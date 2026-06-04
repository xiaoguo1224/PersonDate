from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import InviteCodeStatus, UserRole, UserStatus

json_type = JSON().with_variant(JSONB, "postgresql")


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.MEMBER.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    settings: Mapped[UserSettings] = relationship(back_populates="user", uselist=False)


class UserSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    default_timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Asia/Shanghai"
    )
    workday_start_time: Mapped[str | None] = mapped_column(String(8), default="09:00:00")
    workday_end_time: Mapped[str | None] = mapped_column(String(8), default="18:00:00")
    daily_plan_push_time: Mapped[str | None] = mapped_column(String(8), default="08:00:00")
    default_remind_before_minutes: Mapped[int | None] = mapped_column(Integer, default=0)
    daily_plan_push_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="settings")


class InviteCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=InviteCodeStatus.ACTIVE.value
    )
    remark: Mapped[str | None] = mapped_column(Text)

    usages: Mapped[list[InviteCodeUsage]] = relationship(back_populates="invite_code")


class InviteCodeUsage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invite_code_usages"

    invite_code_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invite_codes.id", ondelete="CASCADE"), nullable=False
    )
    used_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)

    invite_code: Mapped[InviteCode] = relationship(back_populates="usages")
