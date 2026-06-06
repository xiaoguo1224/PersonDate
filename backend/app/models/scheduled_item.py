from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ScheduledItemSource, ScheduledItemStatus


class ScheduledItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_items"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemSource.MANUAL.value
    )
    source_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_items.id", ondelete="SET NULL")
    )
    remind_before_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemStatus.ACTIVE.value
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
