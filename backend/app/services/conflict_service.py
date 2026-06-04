from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalendarEvent,
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
    ScheduleConflict,
)


class ConflictService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def detect_event_conflicts(self, user_id: str, event: CalendarEvent) -> list[ScheduleConflict]:
        event_end_time = event.end_time
        if event_end_time is None:
            return []
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == "active",
            CalendarEvent.id != event.id,
            CalendarEvent.start_time < event_end_time,
            CalendarEvent.end_time > event.start_time,
        )
        conflicts: list[ScheduleConflict] = []
        for other in self.db.scalars(stmt):
            other_end_time = other.end_time
            if other_end_time is None:
                continue
            conflict = ScheduleConflict(
                user_id=user_id,
                conflict_type=ConflictType.TIME_OVERLAP.value,
                severity=ConflictSeverity.HIGH.value,
                title=f"日程冲突：{event.title} 与 {other.title}",
                description=(
                    f"{event.title} 与 {other.title} 的时间重叠，"
                    f"分别是 {event.start_time.isoformat()} - {event_end_time.isoformat()} 和 "
                    f"{other.start_time.isoformat()} - {other_end_time.isoformat()}"
                ),
                related_item_ids={"current": event.id, "other": other.id},
                suggestion="请调整其中一个日程时间，或选择忽略冲突。",
                status=ConflictStatus.OPEN.value,
                detected_at=datetime.now(UTC),
            )
            self.db.add(conflict)
            conflicts.append(conflict)
        return conflicts

    def detect_day_conflicts(self, user_id: str) -> list[ScheduleConflict]:
        stmt = (
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.status == "active",
                CalendarEvent.end_time.is_not(None),
            )
            .order_by(CalendarEvent.start_time.asc())
        )
        events = list(self.db.scalars(stmt))
        conflicts: list[ScheduleConflict] = []
        for index, event in enumerate(events):
            event_end_time = event.end_time
            if event_end_time is None:
                continue
            for other in events[index + 1 :]:
                other_end_time = other.end_time
                if other_end_time is None:
                    continue
                if other.start_time >= event_end_time:
                    break
                conflict = ScheduleConflict(
                    user_id=user_id,
                    conflict_type=ConflictType.TIME_OVERLAP.value,
                    severity=ConflictSeverity.HIGH.value,
                    title=f"日程冲突：{event.title} 与 {other.title}",
                    description="存在时间重叠。",
                    related_item_ids={"current": event.id, "other": other.id},
                    suggestion="请调整其中一个日程时间，或选择忽略冲突。",
                    status=ConflictStatus.OPEN.value,
                    detected_at=datetime.now(UTC),
                )
                self.db.add(conflict)
                conflicts.append(conflict)
        return conflicts

    def list_conflicts(self, user_id: str, status: str | None = None) -> list[ScheduleConflict]:
        stmt = select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)
        if status:
            stmt = stmt.where(ScheduleConflict.status == status)
        return list(self.db.scalars(stmt.order_by(ScheduleConflict.created_at.desc())))

    def get_conflict(self, user_id: str, conflict_id: str) -> ScheduleConflict | None:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.id == conflict_id,
        )
        return self.db.scalar(stmt)

    def ignore_conflict(self, conflict: ScheduleConflict) -> ScheduleConflict:
        conflict.status = ConflictStatus.IGNORED.value
        return conflict

    def resolve_conflict(self, conflict: ScheduleConflict) -> ScheduleConflict:
        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolved_at = datetime.now(UTC)
        return conflict
