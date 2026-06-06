from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CalendarEvent,
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
    EventStatus,
    ScheduleConflict,
)


class ConflictService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _event_has_finished(self, event: CalendarEvent, now: datetime) -> bool:
        event_end_time = event.end_time or event.start_time
        return self._as_utc(event_end_time) <= now

    def _pair_key(self, related_item_ids: dict[str, Any] | None) -> tuple[str, str] | None:
        if not isinstance(related_item_ids, dict):
            return None
        current = related_item_ids.get("current")
        other = related_item_ids.get("other")
        if not isinstance(current, str) or not isinstance(other, str):
            return None
        first, second = sorted((current, other))
        return first, second

    def _has_open_conflict(
        self,
        *,
        user_id: str,
        conflict_type: str,
        related_item_ids: dict[str, Any],
    ) -> bool:
        target_pair = self._pair_key(related_item_ids)
        if target_pair is None:
            return False
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.conflict_type == conflict_type,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        for conflict in self.db.scalars(stmt):
            if self._pair_key(conflict.related_item_ids) == target_pair:
                return True
        return False

    def _has_active_related_events(
        self,
        user_id: str,
        related_item_ids: dict[str, Any] | None,
        *,
        now: datetime,
    ) -> bool:
        target_pair = self._pair_key(related_item_ids)
        if target_pair is None:
            return True
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == EventStatus.ACTIVE.value,
            CalendarEvent.id.in_(target_pair),
        )
        related_events = list(self.db.scalars(stmt))
        if len(related_events) != len(target_pair):
            return False
        return any(not self._event_has_finished(event, now) for event in related_events)

    def _resolve_stale_open_conflicts(self, user_id: str, now: datetime) -> None:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        changed = False
        for conflict in self.db.scalars(stmt):
            if self._has_active_related_events(
                user_id,
                conflict.related_item_ids,
                now=now,
            ):
                continue
            conflict.status = ConflictStatus.RESOLVED.value
            conflict.resolved_at = now
            changed = True
        if changed:
            self.db.flush()

    def _event_sort_key(self, event: CalendarEvent) -> tuple[str, str, str]:
        return (
            event.start_time.isoformat(),
            (event.end_time or event.start_time).isoformat(),
            event.id,
        )

    def _ordered_pair(
        self, first: CalendarEvent, second: CalendarEvent
    ) -> tuple[CalendarEvent, CalendarEvent]:
        first_key = self._event_sort_key(first)
        second_key = self._event_sort_key(second)
        if second_key < first_key:
            return second, first
        return first, second

    def detect_event_conflicts(self, user_id: str, event: CalendarEvent) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
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
            primary, secondary = self._ordered_pair(event, other)
            related_item_ids = {"current": primary.id, "other": secondary.id}
            if self._has_open_conflict(
                user_id=user_id,
                conflict_type=ConflictType.TIME_OVERLAP.value,
                related_item_ids=related_item_ids,
            ):
                continue
            conflict = ScheduleConflict(
                user_id=user_id,
                conflict_type=ConflictType.TIME_OVERLAP.value,
                severity=ConflictSeverity.HIGH.value,
                title=f"日程冲突：{primary.title} 与 {secondary.title}",
                description=(
                    f"{primary.title} 与 {secondary.title} 的时间重叠，"
                    f"分别是 {primary.start_time.isoformat()} - "
                    f"{(primary.end_time or primary.start_time).isoformat()} 和 "
                    f"{secondary.start_time.isoformat()} - "
                    f"{(secondary.end_time or secondary.start_time).isoformat()}"
                ),
                related_item_ids=related_item_ids,
                suggestion="请调整其中一个日程时间，或选择忽略冲突。",
                status=ConflictStatus.OPEN.value,
                detected_at=datetime.now(UTC),
            )
            self.db.add(conflict)
            conflicts.append(conflict)
        self.db.flush()
        return conflicts

    def detect_day_conflicts(self, user_id: str) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
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
                primary, secondary = self._ordered_pair(event, other)
                related_item_ids = {"current": primary.id, "other": secondary.id}
                if self._has_open_conflict(
                    user_id=user_id,
                    conflict_type=ConflictType.TIME_OVERLAP.value,
                    related_item_ids=related_item_ids,
                ):
                    continue
                conflict = ScheduleConflict(
                    user_id=user_id,
                    conflict_type=ConflictType.TIME_OVERLAP.value,
                    severity=ConflictSeverity.HIGH.value,
                    title=f"日程冲突：{primary.title} 与 {secondary.title}",
                    description="存在时间重叠。",
                    related_item_ids=related_item_ids,
                    suggestion="请调整其中一个日程时间，或选择忽略冲突。",
                    status=ConflictStatus.OPEN.value,
                    detected_at=now,
                )
                self.db.add(conflict)
                conflicts.append(conflict)
        self.db.flush()
        return conflicts

    def list_conflicts(self, user_id: str, status: str | None = None) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)
        if status:
            stmt = stmt.where(ScheduleConflict.status == status)
        conflicts = list(self.db.scalars(stmt.order_by(ScheduleConflict.created_at.desc())))
        seen: set[tuple[str, str, tuple[str, str] | None]] = set()
        unique_conflicts: list[ScheduleConflict] = []
        for conflict in conflicts:
            if conflict.status == ConflictStatus.OPEN.value and not self._has_active_related_events(
                user_id,
                conflict.related_item_ids,
                now=now,
            ):
                continue
            pair_key = self._pair_key(conflict.related_item_ids)
            key = (conflict.conflict_type, conflict.status, pair_key)
            if key in seen:
                continue
            seen.add(key)
            unique_conflicts.append(conflict)
        return unique_conflicts

    def resolve_conflicts_for_event(self, user_id: str, event_id: str) -> list[ScheduleConflict]:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        resolved_conflicts: list[ScheduleConflict] = []
        for conflict in self.db.scalars(stmt):
            pair_key = self._pair_key(conflict.related_item_ids)
            if pair_key is None or event_id not in pair_key:
                continue
            conflict.status = ConflictStatus.RESOLVED.value
            conflict.resolved_at = datetime.now(UTC)
            resolved_conflicts.append(conflict)
        self.db.flush()
        return resolved_conflicts

    def get_conflict(self, user_id: str, conflict_id: str) -> ScheduleConflict | None:
        self._resolve_stale_open_conflicts(user_id, datetime.now(UTC))
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
