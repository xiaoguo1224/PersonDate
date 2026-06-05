from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    MessageDirection,
    WechatBindingCode,
)


class WechatStatusSummary(TypedDict):
    connected: bool
    channel_token_configured: bool
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

    def __init__(self, db: Session) -> None:
        self.db = db

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
