from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    MessageDirection,
    WechatAccount,
    WechatChannelInboundMessage,
    WechatChannelOutboundMessage,
    WechatLoginSession,
)
from app.schemas.wechat_channel import (
    WechatChannelMessageItem,
    WechatGetConfigResponse,
    WechatGetUpdatesResponse,
    WechatIngestMessageRequest,
    WechatSendTypingResponse,
)


def _as_utc(datetime_value: datetime) -> datetime:
    if datetime_value.tzinfo is None:
        return datetime_value.replace(tzinfo=UTC)
    return datetime_value.astimezone(UTC)


class WechatStatusSummary(TypedDict):
    connected: bool
    channel_token_configured: bool
    total_accounts: int
    active_accounts: int
    queued_outbound_messages: int
    sent_outbound_messages: int
    failed_outbound_messages: int
    total_identities: int
    active_identities: int
    bound_users: int
    last_message_at: datetime | None
    recent_inbound_messages: list[ChannelMessageLog]
    recent_outbound_messages: list[ChannelMessageLog]


class WechatChannelService:
    LOGIN_SESSION_TTL_MINUTES = 10
    LOG_LIST_LIMIT = 100
    SEND_TEXT_MAX_ATTEMPTS = 3
    SEND_TEXT_RETRYABLE_ERROR_CODES = {
        "TIMEOUT",
        "REQUEST_TIMEOUT",
        "NETWORK_ERROR",
        "CONNECTION_ERROR",
        "TEMPORARY_ERROR",
        "TRANSPORT_ERROR",
    }

    def __init__(self, db: Session, sender: Any | None = None) -> None:
        self.db = db
        self.sender = sender

    def create_login_session(self, owner_user_id: str) -> WechatLoginSession:
        now = datetime.now(UTC)
        login_session_id = f"login_{secrets.token_hex(8)}"
        session = WechatLoginSession(
            owner_user_id=owner_user_id,
            login_session_id=login_session_id,
            qr_payload=f"wechat-qr:{login_session_id}",
            status="qr_created",
            expires_at=now + timedelta(minutes=self.LOGIN_SESSION_TTL_MINUTES),
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_login_session(
        self,
        *,
        owner_user_id: str,
        login_session_id: str,
    ) -> WechatLoginSession | None:
        stmt = select(WechatLoginSession).where(
            WechatLoginSession.owner_user_id == owner_user_id,
            WechatLoginSession.login_session_id == login_session_id,
        )
        return self.db.scalar(stmt)

    def list_accounts(self, owner_user_id: str) -> list[WechatAccount]:
        stmt = (
            select(WechatAccount)
            .where(WechatAccount.owner_user_id == owner_user_id)
            .order_by(WechatAccount.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def get_account_by_account_id(self, account_id: str) -> WechatAccount | None:
        stmt = select(WechatAccount).where(WechatAccount.account_id == account_id)
        return self.db.scalar(stmt)

    def get_account_by_bot_token(self, bot_token: str) -> WechatAccount | None:
        stmt = select(WechatAccount).where(WechatAccount.bot_token == bot_token)
        return self.db.scalar(stmt)

    def list_active_accounts(self) -> list[WechatAccount]:
        stmt = (
            select(WechatAccount)
            .where(WechatAccount.status == "active")
            .order_by(
                WechatAccount.last_active_time.desc().nullslast(),
                WechatAccount.created_at.desc(),
            )
        )
        return list(self.db.scalars(stmt))

    def _resolve_account(
        self,
        *,
        account_id: str | None = None,
        bot_token: str | None = None,
    ) -> WechatAccount | None:
        if account_id is not None:
            return self.get_account_by_account_id(account_id)
        if bot_token is not None:
            return self.get_account_by_bot_token(bot_token)
        return None

    def resolve_account(
        self,
        *,
        account_id: str | None = None,
        bot_token: str | None = None,
    ) -> WechatAccount | None:
        return self._resolve_account(account_id=account_id, bot_token=bot_token)

    def resolve_send_account(
        self,
        *,
        account_id: str | None = None,
        conversation_id: str | None = None,
        to_user_id: str | None = None,
    ) -> WechatAccount | None:
        if account_id is not None:
            account = self.get_account_by_account_id(account_id)
            if account is not None and account.status == "active":
                return account
            return None

        candidate_identity = None
        if conversation_id is not None:
            candidate_identity = self.db.scalar(
                select(ChannelIdentity).where(
                    ChannelIdentity.channel == "wechat",
                    ChannelIdentity.status == "active",
                    ChannelIdentity.conversation_id == conversation_id,
                )
            )
        if candidate_identity is None and to_user_id is not None:
            candidate_identity = self.db.scalar(
                select(ChannelIdentity).where(
                    ChannelIdentity.channel == "wechat",
                    ChannelIdentity.status == "active",
                    ChannelIdentity.channel_user_id == to_user_id,
                )
            )
        if candidate_identity is None:
            return None

        stmt = (
            select(WechatAccount)
            .where(
                WechatAccount.owner_user_id == candidate_identity.user_id,
                WechatAccount.status == "active",
            )
            .order_by(
                WechatAccount.last_active_time.desc().nullslast(),
                WechatAccount.created_at.desc(),
            )
        )
        return self.db.scalar(stmt)

    def confirm_login_session(
        self,
        *,
        owner_user_id: str,
        login_session_id: str,
        account_id: str,
        wechat_user_id: str | None,
        bot_token: str,
        base_url: str,
        remark: str | None = None,
    ) -> tuple[WechatLoginSession, WechatAccount]:
        session = self.get_login_session(
            owner_user_id=owner_user_id,
            login_session_id=login_session_id,
        )
        if session is None:
            raise ValueError("登录会话不存在")
        if _as_utc(session.expires_at) <= datetime.now(UTC):
            session.status = "expired"
            raise ValueError("登录会话已过期")

        account = self.db.scalar(
            select(WechatAccount).where(WechatAccount.account_id == account_id)
        )
        if account is None:
            account = WechatAccount(
                owner_user_id=owner_user_id,
                account_id=account_id,
                wechat_user_id=wechat_user_id,
                bot_token=bot_token,
                base_url=base_url,
                remark=remark,
                status="active",
                bind_time=datetime.now(UTC),
                last_active_time=datetime.now(UTC),
            )
            self.db.add(account)
        else:
            if account.owner_user_id != owner_user_id:
                raise ValueError("通道账号已绑定到其他用户")
            account.wechat_user_id = wechat_user_id
            account.bot_token = bot_token
            account.base_url = base_url
            account.remark = remark
            account.status = "active"
            account.bind_time = datetime.now(UTC)
            account.last_active_time = datetime.now(UTC)

        channel_user_id = wechat_user_id or account_id
        identity = self.db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "wechat",
                ChannelIdentity.channel_user_id == channel_user_id,
            )
        )
        if identity is not None and identity.user_id != owner_user_id:
            raise ValueError("该微信身份已绑定到其他用户")
        if identity is None:
            identity = ChannelIdentity(
                user_id=owner_user_id,
                channel="wechat",
                channel_user_id=channel_user_id,
                conversation_id=channel_user_id,
                display_name=remark,
                status="active",
                bound_at=datetime.now(UTC),
            )
            self.db.add(identity)
        else:
            identity.user_id = owner_user_id
            identity.channel = "wechat"
            identity.conversation_id = channel_user_id
            if remark is not None:
                identity.display_name = remark
            identity.status = "active"
            identity.bound_at = datetime.now(UTC)

        session.status = "confirmed"
        session.confirmed_at = datetime.now(UTC)
        self.db.flush()
        return session, account

    def get_message_log_by_message_id(
        self,
        message_id: str,
        account_id: str | None = None,
    ) -> ChannelMessageLog | None:
        stmt = select(ChannelMessageLog).where(
            ChannelMessageLog.channel == "wechat",
            ChannelMessageLog.message_id == message_id,
        )
        if account_id is not None:
            stmt = stmt.where(ChannelMessageLog.account_id == account_id)
        return self.db.scalar(stmt.order_by(ChannelMessageLog.created_at.desc()))

    def list_identities(self, user_id: str) -> list[ChannelIdentity]:
        stmt = (
            select(ChannelIdentity)
            .where(ChannelIdentity.user_id == user_id)
            .order_by(ChannelIdentity.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def disable_identity(self, user_id: str, identity_id: str) -> ChannelIdentity | None:
        identity = self.db.get(ChannelIdentity, identity_id)
        if identity is None or identity.user_id != user_id:
            return None
        identity.status = "disabled"
        return identity

    def update_account_cursor(
        self,
        *,
        account_id: str,
        cursor: str | None,
        last_active_time: datetime | None = None,
    ) -> WechatAccount | None:
        account = self.get_account_by_account_id(account_id)
        if account is None:
            return None
        account.cursor = cursor
        account.last_active_time = last_active_time or datetime.now(UTC)
        return account

    def update_account_status(
        self,
        *,
        account_id: str,
        status: str,
        last_active_time: datetime | None = None,
    ) -> WechatAccount | None:
        account = self.get_account_by_account_id(account_id)
        if account is None:
            return None
        account.status = status
        account.last_active_time = last_active_time or datetime.now(UTC)
        return account

    def enqueue_inbound_message(
        self,
        *,
        account_id: str,
        message_id: str | None,
        conversation_id: str,
        channel_user_id: str,
        display_name: str | None = None,
        content_type: str = "text",
        content: str | None = None,
        context_token: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> WechatChannelInboundMessage:
        if message_id is None:
            message_id = f"wx_msg_{secrets.token_hex(8)}"
        message = WechatChannelInboundMessage(
            account_id=account_id,
            message_id=message_id,
            cursor_token=self._build_cursor_token(),
            conversation_id=conversation_id,
            channel_user_id=channel_user_id,
            display_name=display_name,
            content_type=content_type,
            content=content,
            context_token=context_token,
            raw_payload=raw_payload or {},
            status="pending",
        )
        self.db.add(message)
        self.db.flush()
        return message

    def ingest_message(
        self,
        payload: WechatIngestMessageRequest,
    ) -> tuple[WechatChannelInboundMessage, bool]:
        account = self.get_account_by_account_id(payload.account_id)
        if account is None:
            raise ValueError("微信账号不存在或未绑定")

        existing = self.db.scalar(
            select(WechatChannelInboundMessage).where(
                WechatChannelInboundMessage.account_id == payload.account_id,
                WechatChannelInboundMessage.message_id == payload.message_id,
            )
        )
        if existing is not None:
            return existing, True

        message = self.enqueue_inbound_message(
            account_id=payload.account_id,
            message_id=payload.message_id,
            conversation_id=payload.conversation_id,
            channel_user_id=payload.channel_user_id,
            display_name=payload.display_name,
            content_type=payload.content_type,
            content=payload.content,
            context_token=payload.context_token,
            raw_payload=payload.raw_payload,
        )
        account.last_active_time = datetime.now(UTC)
        return message, False

    def get_updates(
        self,
        *,
        bot_token: str | None = None,
        account_id: str | None = None,
        get_updates_buf: str | None = None,
    ) -> WechatGetUpdatesResponse:
        account = self._resolve_account(account_id=account_id, bot_token=bot_token)
        if account is None:
            if account_id is None and bot_token is None:
                return WechatGetUpdatesResponse(
                    success=True,
                    ret=0,
                    messages=[],
                    next_cursor=get_updates_buf or "",
                    longpolling_timeout_ms=35000,
                )
            return WechatGetUpdatesResponse(
                success=False,
                ret=-1,
                messages=[],
                next_cursor=get_updates_buf or "",
                error_code="ACCOUNT_NOT_FOUND",
                error_message="微信账号不存在或未绑定",
                longpolling_timeout_ms=35000,
            )

        cursor = get_updates_buf or account.cursor or ""
        stmt = select(WechatChannelInboundMessage).where(
            WechatChannelInboundMessage.account_id == account.account_id,
        )
        if cursor:
            stmt = stmt.where(WechatChannelInboundMessage.cursor_token > cursor)
        stmt = stmt.order_by(WechatChannelInboundMessage.cursor_token.asc()).limit(50)
        messages = list(self.db.scalars(stmt))
        if messages:
            delivered_at = datetime.now(UTC)
            for message in messages:
                message.status = "delivered"
                message.delivered_at = delivered_at

        return WechatGetUpdatesResponse(
            success=True,
            ret=0,
            messages=[self._to_inbound_item(message) for message in messages],
            next_cursor=messages[-1].cursor_token if messages else cursor,
            longpolling_timeout_ms=35000,
        )

    def get_config(
        self,
        *,
        account_id: str | None = None,
        bot_token: str | None = None,
    ) -> WechatGetConfigResponse:
        account = self._resolve_account(account_id=account_id, bot_token=bot_token)
        if account is None:
            if account_id is None and bot_token is None:
                return WechatGetConfigResponse(
                    success=True,
                    ret=0,
                    status="idle",
                    cursor=None,
                    remark=None,
                    typing_ticket=None,
                )
            return WechatGetConfigResponse(
                success=False,
                ret=-1,
                error_code="ACCOUNT_NOT_FOUND",
                error_message="微信账号不存在或未绑定",
            )

        return WechatGetConfigResponse(
            success=True,
            ret=0,
            account_id=account.account_id,
            status=account.status,
            cursor=account.cursor,
            remark=account.remark,
            typing_ticket=self._build_typing_ticket(account),
        )

    def send_typing(
        self,
        *,
        conversation_id: str,
        typing: bool,
        account_id: str | None = None,
        bot_token: str | None = None,
        typing_ticket: str | None = None,
    ) -> WechatSendTypingResponse:
        account = self._resolve_account(account_id=account_id, bot_token=bot_token)
        if account is None:
            if account_id is None and bot_token is None:
                return WechatSendTypingResponse(success=True, ret=0, typing=typing)
            return WechatSendTypingResponse(
                success=False,
                ret=-1,
                typing=typing,
                error_code="ACCOUNT_NOT_FOUND",
                error_message="微信账号不存在或未绑定",
            )

        expected_ticket = self._build_typing_ticket(account)
        if typing_ticket is not None and typing_ticket != expected_ticket:
            return WechatSendTypingResponse(
                success=False,
                ret=-1,
                typing=typing,
                error_code="INVALID_TYPING_TICKET",
                error_message="typing_ticket 无效",
            )

        return WechatSendTypingResponse(success=True, ret=0, typing=typing)

    def list_message_logs(
        self,
        *,
        user_id: str | None = None,
        account_id: str | None = None,
        conversation_id: str | None = None,
        direction: str | None = None,
        limit: int = LOG_LIST_LIMIT,
    ) -> list[ChannelMessageLog]:
        stmt = select(ChannelMessageLog)
        if user_id is not None:
            stmt = stmt.where(ChannelMessageLog.user_id == user_id)
        if account_id is not None:
            stmt = stmt.where(ChannelMessageLog.account_id == account_id)
        if conversation_id is not None:
            stmt = stmt.where(ChannelMessageLog.conversation_id == conversation_id)
        if direction is not None:
            stmt = stmt.where(ChannelMessageLog.direction == direction)
        stmt = stmt.order_by(ChannelMessageLog.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def list_outbound_messages(
        self,
        *,
        account_id: str | None = None,
        conversation_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WechatChannelOutboundMessage]:
        stmt = select(WechatChannelOutboundMessage)
        if account_id is not None:
            stmt = stmt.where(WechatChannelOutboundMessage.account_id == account_id)
        if conversation_id is not None:
            stmt = stmt.where(
                WechatChannelOutboundMessage.conversation_id == conversation_id,
            )
        if status is not None:
            stmt = stmt.where(WechatChannelOutboundMessage.status == status)
        stmt = stmt.order_by(WechatChannelOutboundMessage.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def create_message_log(
        self,
        *,
        user_id: str | None,
        account_id: str | None = None,
        message_id: str | None,
        conversation_id: str,
        channel_user_id: str | None,
        direction: str,
        content_type: str,
        content: str | None,
        context_token: str | None = None,
        raw_payload: dict[str, object] | None = None,
        status: str = "received",
        retry_count: int = 0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ChannelMessageLog:
        log = ChannelMessageLog(
            user_id=user_id,
            channel="wechat",
            account_id=account_id,
            message_id=message_id,
            conversation_id=conversation_id,
            channel_user_id=channel_user_id,
            direction=direction,
            content_type=content_type,
            content=content,
            context_token=context_token,
            raw_payload=raw_payload or {},
            status=status,
            retry_count=retry_count,
            error_code=error_code,
            error_message=error_message,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def send_text(
        self,
        *,
        conversation_id: str,
        content: str,
        context_token: str | None = None,
        user_id: str | None = None,
        channel_user_id: str | None = None,
        message_id: str | None = None,
        retry_count: int = 0,
    ) -> ChannelMessageLog:
        identity = self.db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "wechat",
                ChannelIdentity.conversation_id == conversation_id,
                ChannelIdentity.status == "active",
            )
        )
        resolved_user_id = user_id or (identity.user_id if identity else None)
        resolved_channel_user_id = channel_user_id or (
            identity.channel_user_id if identity else None
        )
        resolved_context_token = context_token or self._resolve_context_token(conversation_id)

        outbound_message_id = message_id
        status = "failed"
        error_message: str | None = None
        error_code: str | None = None
        outbound_retry_count = retry_count
        attempt_count = 0
        while attempt_count < self.SEND_TEXT_MAX_ATTEMPTS:
            attempt_count += 1
            try:
                if self.sender is None:
                    raise RuntimeError("微信发送适配器未配置")
                result = self._send_text_to_channel(
                    conversation_id=conversation_id,
                    content=content,
                    context_token=resolved_context_token,
                )
                if isinstance(result, dict):
                    success = bool(result.get("success", True))
                    result_status = result.get("status")
                    outbound_message_id = result.get("message_id") or outbound_message_id
                    error_message = result.get("error_message") or result.get("detail")
                    error_code = result.get("error_code")
                else:
                    success = bool(getattr(result, "success", True))
                    result_status = getattr(result, "status", None)
                    outbound_message_id = (
                        getattr(result, "message_id", None) or outbound_message_id
                    )
                    error_message = getattr(result, "error_message", None)
                    error_code = getattr(result, "error_code", None)
                if success:
                    status = result_status or "sent"
                    error_message = None
                    error_code = None
                    outbound_retry_count = retry_count + attempt_count - 1
                    break
                error_message = error_message or "微信消息发送失败"
                error_code = error_code or "SEND_FAILED"
                if (
                    not self._is_retryable_send_failure(error_code, error_message)
                    or attempt_count >= self.SEND_TEXT_MAX_ATTEMPTS
                ):
                    outbound_retry_count = retry_count + attempt_count - 1
                    break
            except Exception as exc:  # noqa: BLE001
                error_message = str(exc)
                error_code = exc.__class__.__name__.upper()
                if (
                    not self._is_retryable_send_exception(exc)
                    or attempt_count >= self.SEND_TEXT_MAX_ATTEMPTS
                ):
                    outbound_retry_count = retry_count + attempt_count - 1
                    break
        else:
            outbound_retry_count = retry_count + self.SEND_TEXT_MAX_ATTEMPTS - 1

        return self.create_message_log(
            user_id=resolved_user_id,
            message_id=outbound_message_id,
            conversation_id=conversation_id,
            channel_user_id=resolved_channel_user_id,
            direction=MessageDirection.OUTBOUND.value,
            content_type="text",
            content=content,
            context_token=resolved_context_token,
            raw_payload={
                "conversation_id": conversation_id,
                "content": content,
                "context_token": resolved_context_token,
            },
            status=status,
            retry_count=outbound_retry_count,
            error_code=error_code,
            error_message=error_message,
        )

    def create_outbound_message(
        self,
        *,
        account: WechatAccount,
        to_user_id: str,
        conversation_id: str,
        content: str,
        context_token: str | None = None,
        raw_payload: dict[str, object] | None = None,
        message_id: str | None = None,
        status: str = "queued",
        retry_count: int = 0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> WechatChannelOutboundMessage:
        outbound = WechatChannelOutboundMessage(
            account_id=account.account_id,
            message_id=(
                message_id
                or f"wx_out_{int(datetime.now(UTC).timestamp() * 1000)}_{secrets.token_hex(4)}"
            ),
            to_user_id=to_user_id,
            conversation_id=conversation_id,
            content=content,
            context_token=context_token,
            raw_payload=raw_payload or {},
            status=status,
            retry_count=retry_count,
            error_code=error_code,
            error_message=error_message,
            sent_at=datetime.now(UTC) if status == "sent" else None,
        )
        self.db.add(outbound)
        self.db.flush()
        return outbound

    def list_queued_outbound_messages(
        self,
        *,
        account_id: str | None = None,
        limit: int = 50,
    ) -> list[WechatChannelOutboundMessage]:
        stmt = select(WechatChannelOutboundMessage).where(
            WechatChannelOutboundMessage.status == "queued",
        )
        if account_id is not None:
            stmt = stmt.where(WechatChannelOutboundMessage.account_id == account_id)
        stmt = stmt.order_by(
            WechatChannelOutboundMessage.created_at.asc(),
            WechatChannelOutboundMessage.id.asc(),
        ).limit(limit)
        return list(self.db.scalars(stmt))

    def dispatch_outbound_messages_once(self, *, limit: int = 50) -> int:
        queued_messages = self.list_queued_outbound_messages(limit=limit)
        if not queued_messages:
            return 0

        dispatched_count = 0
        now = datetime.now(UTC)
        for message in queued_messages:
            account = self.get_account_by_account_id(message.account_id)
            if account is None or account.status != "active":
                message.status = "failed"
                message.error_code = "ACCOUNT_NOT_AVAILABLE"
                message.error_message = "微信账号当前不可用"
                self._sync_outbound_message_log(
                    account_id=message.account_id,
                    message_id=message.message_id,
                    status="failed",
                    retry_count=message.retry_count,
                    error_code=message.error_code,
                    error_message=message.error_message,
                )
                continue

            message.status = "sent"
            message.sent_at = now
            message.error_code = None
            message.error_message = None
            account.last_active_time = now
            self._sync_outbound_message_log(
                account_id=message.account_id,
                message_id=message.message_id,
                status="sent",
                retry_count=message.retry_count,
                error_code=None,
                error_message=None,
            )
            dispatched_count += 1

        self.db.flush()
        return dispatched_count

    def get_status_summary(self, *, recent_limit: int = 10) -> WechatStatusSummary:
        settings = get_settings()
        channel_token_configured = bool(settings.wechat_channel_token)

        total_identities = self.db.scalar(select(func.count()).select_from(ChannelIdentity)) or 0
        active_identities = (
            self.db.scalar(
                select(func.count())
                .select_from(ChannelIdentity)
                .where(ChannelIdentity.status == "active")
            )
            or 0
        )
        total_accounts = self.db.scalar(select(func.count()).select_from(WechatAccount)) or 0
        active_accounts = (
            self.db.scalar(
                select(func.count())
                .select_from(WechatAccount)
                .where(WechatAccount.status == "active")
            )
            or 0
        )
        queued_outbound_messages = (
            self.db.scalar(
                select(func.count())
                .select_from(WechatChannelOutboundMessage)
                .where(WechatChannelOutboundMessage.status == "queued")
            )
            or 0
        )
        sent_outbound_messages = (
            self.db.scalar(
                select(func.count())
                .select_from(WechatChannelOutboundMessage)
                .where(WechatChannelOutboundMessage.status == "sent")
            )
            or 0
        )
        failed_outbound_messages = (
            self.db.scalar(
                select(func.count())
                .select_from(WechatChannelOutboundMessage)
                .where(WechatChannelOutboundMessage.status == "failed")
            )
            or 0
        )
        bound_users = (
            self.db.scalar(
                select(func.count(func.distinct(ChannelIdentity.user_id)))
                .select_from(ChannelIdentity)
                .where(ChannelIdentity.status == "active")
            )
            or 0
        )
        last_message_at = self.db.scalar(select(func.max(ChannelMessageLog.created_at)))
        recent_inbound_messages = self.list_message_logs(
            direction=MessageDirection.INBOUND.value,
            limit=recent_limit,
        )
        recent_outbound_messages = self.list_message_logs(
            direction=MessageDirection.OUTBOUND.value,
            limit=recent_limit,
        )
        return {
            "connected": channel_token_configured,
            "channel_token_configured": channel_token_configured,
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "queued_outbound_messages": queued_outbound_messages,
            "sent_outbound_messages": sent_outbound_messages,
            "failed_outbound_messages": failed_outbound_messages,
            "total_identities": total_identities,
            "active_identities": active_identities,
            "bound_users": bound_users,
            "last_message_at": last_message_at,
            "recent_inbound_messages": recent_inbound_messages,
            "recent_outbound_messages": recent_outbound_messages,
        }

    def to_account_item(self, account: WechatAccount) -> dict[str, Any]:
        return {
            "id": account.id,
            "owner_user_id": account.owner_user_id,
            "account_id": account.account_id,
            "wechat_user_id": account.wechat_user_id,
            "base_url": account.base_url,
            "cursor": account.cursor,
            "remark": account.remark,
            "status": account.status,
            "bind_time": account.bind_time,
            "last_active_time": account.last_active_time,
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def _build_cursor_token(self) -> str:
        timestamp = int(datetime.now(UTC).timestamp() * 1000)
        return f"{timestamp:013d}_{secrets.token_hex(8)}"

    def _build_typing_ticket(self, account: WechatAccount) -> str:
        digest = hashlib.sha256(
            f"{account.account_id}:{account.bot_token}".encode()
        ).hexdigest()
        return f"typing_{digest[:32]}"

    def _to_inbound_item(
        self,
        message: WechatChannelInboundMessage,
    ) -> WechatChannelMessageItem:
        return WechatChannelMessageItem(
            message_id=message.message_id,
            from_user_id=message.channel_user_id,
            to_user_id=message.account_id,
            session_id=message.conversation_id,
            conversation_id=message.conversation_id,
            channel_user_id=message.channel_user_id,
            display_name=message.display_name,
            content_type=message.content_type,
            content=message.content,
            context_token=message.context_token,
            raw_payload=message.raw_payload or {},
        )

    def _send_text_to_channel(
        self,
        *,
        conversation_id: str,
        content: str,
        context_token: str | None,
    ) -> Any:
        sender = self.sender
        if sender is None:
            raise RuntimeError("微信发送适配器未配置")

        if context_token is None:
            return sender.send_text(conversation_id, content)
        try:
            return sender.send_text(
                conversation_id,
                content,
                context_token=context_token,
            )
        except TypeError as exc:
            try:
                return sender.send_text(conversation_id, content)
            except TypeError:
                raise exc from None

    def _resolve_context_token(self, conversation_id: str) -> str | None:
        stmt = (
            select(ChannelMessageLog.context_token)
            .where(
                ChannelMessageLog.channel == "wechat",
                ChannelMessageLog.conversation_id == conversation_id,
                ChannelMessageLog.direction == MessageDirection.INBOUND.value,
                ChannelMessageLog.context_token.isnot(None),
            )
            .order_by(ChannelMessageLog.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _sync_outbound_message_log(
        self,
        *,
        account_id: str,
        message_id: str,
        status: str,
        retry_count: int,
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        log = self.db.scalar(
            select(ChannelMessageLog).where(
                ChannelMessageLog.channel == "wechat",
                ChannelMessageLog.account_id == account_id,
                ChannelMessageLog.message_id == message_id,
                ChannelMessageLog.direction == MessageDirection.OUTBOUND.value,
            )
        )
        if log is None:
            return
        log.status = status
        log.retry_count = retry_count
        log.error_code = error_code
        log.error_message = error_message

    def _is_retryable_send_failure(self, error_code: str | None, error_message: str | None) -> bool:
        if error_code is not None and error_code.upper() in self.SEND_TEXT_RETRYABLE_ERROR_CODES:
            return True
        if error_message is None:
            return False
        lowered = error_message.lower()
        return any(
            keyword in lowered
            for keyword in ("timeout", "timed out", "network", "temporary")
        )

    def _is_retryable_send_exception(self, exc: Exception) -> bool:
        return isinstance(
            exc,
            (
                TimeoutError,
                ConnectionError,
                httpx.TimeoutException,
                httpx.TransportError,
            ),
        )
