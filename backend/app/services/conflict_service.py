from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.models import ConflictSeverity, ConflictStatus, ConflictType, ScheduleConflict
from app.models.enums import ScheduledItemStatus
from app.models.scheduled_item import ScheduledItem


class ConflictService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _item_has_finished(self, item: ScheduledItem, now: datetime) -> bool:
        return self._as_utc(item.end_time) <= now  # noqa: SIM300

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

    def _has_active_related_items(
        self,
        user_id: str,
        related_item_ids: dict[str, Any] | None,
        *,
        now: datetime,
    ) -> bool:
        target_pair = self._pair_key(related_item_ids)
        if target_pair is None:
            return True
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
            ScheduledItem.id.in_(target_pair),
        )
        related_items = list(self.db.scalars(stmt))
        if len(related_items) != len(target_pair):
            return False
        return any(not self._item_has_finished(item, now) for item in related_items)

    def _resolve_stale_open_conflicts(self, user_id: str, now: datetime) -> None:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        changed = False
        for conflict in self.db.scalars(stmt):
            if self._has_active_related_items(
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

    def _item_sort_key(self, item: ScheduledItem) -> tuple[str, str, str]:
        return (item.start_time.isoformat(), item.end_time.isoformat(), item.id)

    def _ordered_pair(
        self, first: ScheduledItem, second: ScheduledItem
    ) -> tuple[ScheduledItem, ScheduledItem]:
        first_key = self._item_sort_key(first)
        second_key = self._item_sort_key(second)
        if second_key < first_key:
            return second, first
        return first, second

    def detect_item_conflicts(
        self, user_id: str, item: ScheduledItem
    ) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.status == "active",
            ScheduledItem.id != item.id,
            ScheduledItem.start_time < item.end_time,
            ScheduledItem.end_time > item.start_time,
        )
        conflicts: list[ScheduleConflict] = []
        for other in self.db.scalars(stmt):
            primary, secondary = self._ordered_pair(item, other)
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
                title=f"安排冲突：{primary.title} 与 {secondary.title}",
                description=f"{primary.title} 与 {secondary.title} 的时间存在重叠。",
                related_item_ids=related_item_ids,
                suggestion="请调整其中一个安排时间，或选择忽略冲突。",
                status=ConflictStatus.OPEN.value,
                detected_at=datetime.now(UTC),
            )
            self.db.add(conflict)
            conflicts.append(conflict)
        self.db.flush()
        logger.info("检测日程冲突 user_id=%s item_id=%s 新增冲突数=%d", user_id, item.id, len(conflicts))
        return conflicts

    def detect_day_conflicts(self, user_id: str) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = (
            select(ScheduledItem)
            .where(
                ScheduledItem.user_id == user_id,
                ScheduledItem.status == "active",
            )
            .order_by(ScheduledItem.start_time.asc())
        )
        items = list(self.db.scalars(stmt))
        conflicts: list[ScheduleConflict] = []
        for index, item in enumerate(items):
            for other in items[index + 1 :]:
                if other.start_time >= item.end_time:
                    break
                primary, secondary = self._ordered_pair(item, other)
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
                    title=f"安排冲突：{primary.title} 与 {secondary.title}",
                    description="存在时间重叠。",
                    related_item_ids=related_item_ids,
                    suggestion="请调整其中一个安排时间，或选择忽略冲突。",
                    status=ConflictStatus.OPEN.value,
                    detected_at=now,
                )
                self.db.add(conflict)
                conflicts.append(conflict)
        self.db.flush()
        logger.info("检测全天冲突 user_id=%s 新增冲突数=%d", user_id, len(conflicts))
        return conflicts

    def list_conflicts(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScheduleConflict], int]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)
        if status:
            stmt = stmt.where(ScheduleConflict.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                (ScheduleConflict.title.ilike(pattern)) | (ScheduleConflict.description.ilike(pattern))
            )
        conflicts = list(self.db.scalars(stmt.order_by(ScheduleConflict.created_at.desc())))
        seen: set[tuple[str, str, tuple[str, str] | None]] = set()
        unique_conflicts: list[ScheduleConflict] = []
        for conflict in conflicts:
            # 只对 open 状态的冲突检查关联项是否活跃
            # 如果关联项已结束，自动标记为 resolved
            if conflict.status == ConflictStatus.OPEN.value:
                if not self._has_active_related_items(user_id, conflict.related_item_ids, now=now):
                    conflict.status = ConflictStatus.RESOLVED.value
                    conflict.resolved_at = now
                    continue
            pair_key = self._pair_key(conflict.related_item_ids)
            key = (conflict.conflict_type, conflict.status, pair_key)
            if key in seen:
                continue
            seen.add(key)
            unique_conflicts.append(conflict)
        total = len(unique_conflicts)
        start = (page - 1) * page_size
        return unique_conflicts[start : start + page_size], total

    def resolve_conflicts_for_item(self, user_id: str, item_id: str) -> list[ScheduleConflict]:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        resolved_conflicts: list[ScheduleConflict] = []
        for conflict in self.db.scalars(stmt):
            pair_key = self._pair_key(conflict.related_item_ids)
            if pair_key is None or item_id not in pair_key:
                continue
            conflict.status = ConflictStatus.RESOLVED.value
            conflict.resolved_at = datetime.now(UTC)
            resolved_conflicts.append(conflict)
        self.db.flush()
        logger.info("解决项目冲突 user_id=%s item_id=%s 解决数=%d", user_id, item_id, len(resolved_conflicts))
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
        logger.info("忽略冲突 user_id=%s conflict_id=%s", conflict.user_id, conflict.id)
        return conflict

    def resolve_conflict(self, conflict: ScheduleConflict) -> ScheduleConflict:
        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolved_at = datetime.now(UTC)
        logger.info("解决冲突 user_id=%s conflict_id=%s", conflict.user_id, conflict.id)
        return conflict
