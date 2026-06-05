from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    MessageDirection,
    WechatAccount,
    WechatBindingCode,
    WechatLoginSession,
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
    total_identities: int
    active_identities: int
    bound_users: int
    last_message_at: datetime | None
    recent_inbound_messages: list[ChannelMessageLog]
    recent_outbound_messages: list[ChannelMessageLog]


class WechatChannelService:
    BINDING_CODE_TTL_MINUTES = 10
    BINDING_CODE_LENGTH = 6
    BINDING_CODE_RETRY_LIMIT = 20
    LOG_LIST_LIMIT = 100

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
            expires_at=now + timedelta(minutes=self.BINDING_CODE_TTL_MINUTES),
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

    def get_message_log_by_message_id(self, message_id: str) -> ChannelMessageLog | None:
        stmt = select(ChannelMessageLog).where(
            ChannelMessageLog.channel == "wechat",
            ChannelMessageLog.message_id == message_id,
        )
        return self.db.scalar(stmt.order_by(ChannelMessageLog.created_at.desc()))

    def generate_binding_code(self, user_id: str) -> WechatBindingCode:
        now = datetime.now(UTC)
        self._refresh_binding_code_statuses(user_id=user_id, now=now)

        latest_active = self.db.scalar(
            select(WechatBindingCode)
            .where(
                WechatBindingCode.user_id == user_id,
                WechatBindingCode.status == "active",
                WechatBindingCode.expires_at > now,
            )
            .order_by(WechatBindingCode.created_at.desc())
        )
        if latest_active is not None:
            return latest_active

        expires_at = now + timedelta(minutes=self.BINDING_CODE_TTL_MINUTES)
        for _ in range(self.BINDING_CODE_RETRY_LIMIT):
            random_number = secrets.randbelow(10 ** self.BINDING_CODE_LENGTH)
            code = f"{random_number:0{self.BINDING_CODE_LENGTH}d}"
            exists = self.db.scalar(
                select(WechatBindingCode.id).where(WechatBindingCode.code == code)
            )
            if exists is not None:
                continue

            binding_code = WechatBindingCode(
                user_id=user_id,
                code=code,
                expires_at=expires_at,
                status="active",
            )
            self.db.add(binding_code)
            self.db.flush()
            return binding_code

        raise RuntimeError("生成微信绑定码失败，请稍后重试")

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

    def list_message_logs(
        self,
        *,
        user_id: str | None = None,
        conversation_id: str | None = None,
        direction: str | None = None,
        limit: int = LOG_LIST_LIMIT,
    ) -> list[ChannelMessageLog]:
        stmt = select(ChannelMessageLog)
        if user_id is not None:
            stmt = stmt.where(ChannelMessageLog.user_id == user_id)
        if conversation_id is not None:
            stmt = stmt.where(ChannelMessageLog.conversation_id == conversation_id)
        if direction is not None:
            stmt = stmt.where(ChannelMessageLog.direction == direction)
        stmt = stmt.order_by(ChannelMessageLog.created_at.desc()).limit(limit)
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
        raw_payload: dict[str, object] | None = None,
        status: str = "received",
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
            raw_payload=raw_payload or {},
            status=status,
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
        user_id: str | None = None,
        channel_user_id: str | None = None,
        message_id: str | None = None,
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

        status = "sent"
        error_message: str | None = None
        outbound_message_id = message_id
        try:
            if self.sender is None:
                raise RuntimeError("微信发送适配器未配置")
            result = self.sender.send_text(conversation_id, content)
            if isinstance(result, dict):
                success = bool(result.get("success", True))
                outbound_message_id = result.get("message_id") or outbound_message_id
                error_message = result.get("error_message") or result.get("detail")
            else:
                success = bool(getattr(result, "success", True))
                outbound_message_id = getattr(result, "message_id", None) or outbound_message_id
                error_message = getattr(result, "error_message", None)
            if not success:
                status = "failed"
                error_message = error_message or "微信消息发送失败"
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            error_message = str(exc)

        return self.create_message_log(
            user_id=resolved_user_id,
            message_id=outbound_message_id,
            conversation_id=conversation_id,
            channel_user_id=resolved_channel_user_id,
            direction=MessageDirection.OUTBOUND.value,
            content_type="text",
            content=content,
            raw_payload={"conversation_id": conversation_id, "content": content},
            status=status,
            error_message=error_message,
        )

    def consume_binding_code(self, code: str) -> WechatBindingCode | None:
        now = datetime.now(UTC)
        binding_code = self.db.scalar(
            select(WechatBindingCode).where(WechatBindingCode.code == code)
        )
        if binding_code is None:
            return None
        if binding_code.status == "used":
            return None
        if binding_code.status == "disabled":
            return None
        if _as_utc(binding_code.expires_at) <= now:
            binding_code.status = "expired"
            return None
        binding_code.status = "used"
        binding_code.used_at = now
        return binding_code

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
            "total_identities": total_identities,
            "active_identities": active_identities,
            "bound_users": bound_users,
            "last_message_at": last_message_at,
            "recent_inbound_messages": recent_inbound_messages,
            "recent_outbound_messages": recent_outbound_messages,
        }

    def _refresh_binding_code_statuses(self, *, user_id: str, now: datetime) -> None:
        stmt = select(WechatBindingCode).where(
            WechatBindingCode.user_id == user_id,
            WechatBindingCode.status == "active",
        )
        for binding_code in self.db.scalars(stmt):
            if binding_code.expires_at <= now:
                binding_code.status = "expired"
