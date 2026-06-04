from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
    DayPlanStatus,
    EventStatus,
    PlanItemStatus,
    PlanItemType,
    ReminderStatus,
    ReminderTargetType,
    ScheduleSource,
    TaskPriority,
    TaskStatus,
)

json_type = JSON().with_variant(JSONB, "postgresql")


class CalendarEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "calendar_events"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduleSource.AGENT.value
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=EventStatus.ACTIVE.value
    )
    repeat_rule: Mapped[str | None] = mapped_column(Text)
    external_calendar_id: Mapped[str | None] = mapped_column(String(255))
    external_event_id: Mapped[str | None] = mapped_column(String(255))
    created_by_channel: Mapped[str | None] = mapped_column(String(32))
    remind_before_minutes: Mapped[int | None] = mapped_column(Integer, default=0)


class TaskItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "task_items"

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


class DayPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "day_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "plan_date", "status", name="uq_day_plan_active"),
        Index("ix_day_plans_user_date", "user_id", "plan_date"),
        Index("ix_day_plans_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DayPlanStatus.DRAFT.value
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduleSource.AGENT.value
    )

    items: Mapped[list[PlanItem]] = relationship(back_populates="day_plan")


class PlanItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plan_items"
    __table_args__ = (
        Index("ix_plan_items_day_plan", "day_plan_id"),
        Index("ix_plan_items_user", "user_id"),
    )

    day_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("day_plans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PlanItemType.OTHER.value
    )
    ref_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PlanItemStatus.PLANNED.value
    )
    is_flexible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)

    day_plan: Mapped[DayPlan] = relationship(back_populates="items")


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
        String(64), nullable=False, default=ReminderTargetType.EVENT.value
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReminderStatus.PENDING.value
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
