from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ChannelType, ContentType

json_type = JSON().with_variant(JSONB, "postgresql")


class ChannelIdentity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "channel_identities"
    __table_args__ = (
        UniqueConstraint("channel", "channel_user_id", name="uq_channel_user"),
        UniqueConstraint("channel", "conversation_id", name="uq_channel_conversation"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ChannelType.WECHAT.value
    )
    channel_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WechatAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "wechat_accounts"

    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    wechat_user_id: Mapped[str | None] = mapped_column(String(255))
    bot_token: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    cursor: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    bind_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_active_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )


class WechatLoginSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "wechat_login_sessions"

    owner_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    login_session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    qr_payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChannelMessageLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "channel_message_logs"
    __table_args__ = (
        UniqueConstraint("channel", "account_id", "message_id", name="uq_channel_account_message"),
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ChannelType.WECHAT.value
    )
    message_id: Mapped[str | None] = mapped_column(String(255))
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_user_id: Mapped[str | None] = mapped_column(String(255))
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ContentType.TEXT.value
    )
    content: Mapped[str | None] = mapped_column(Text)
    context_token: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(String(255), index=True)
