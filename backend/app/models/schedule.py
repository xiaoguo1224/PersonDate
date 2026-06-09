from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Date, ForeignKey, Index, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
    ReminderStatus,
    ReminderTargetType,
    ScheduleSource,
    ScheduledItemSource,
    ScheduledItemStatus,
    TaskPriority,
    TaskStatus,
)

json_type = JSON().with_variant(JSONB, "postgresql")


class ScheduleConflict(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedule_conflicts"
    __table_args__ = (
        Index("ix_conflicts_user_status", "user_id", "status"),
        Index("ix_conflicts_user_type", "user_id", "conflict_type"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conflict_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ConflictType.TIME_OVERLAP.value
    )
    severity: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConflictSeverity.MEDIUM.value
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    related_item_ids: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    suggestion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConflictStatus.OPEN.value
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "task_items"
    __table_args__ = (
        Index("ix_task_items_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TaskPriority.MEDIUM.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TaskStatus.PENDING.value
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduleSource.AGENT.value
    )
    schedule_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scheduled_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    scheduled_end_time: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    completed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReminderJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reminder_jobs"
    __table_args__ = (
        Index("ix_reminders_user_status", "user_id", "status"),
        Index("ix_reminders_trigger_time", "trigger_time"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ReminderTargetType.SCHEDULED_ITEM.value
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReminderStatus.PENDING.value
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
