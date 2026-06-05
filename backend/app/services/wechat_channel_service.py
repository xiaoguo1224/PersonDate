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
    LOGIN_SESSION_TTL_MINUTES = 10
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
