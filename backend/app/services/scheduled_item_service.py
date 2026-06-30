from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_events
from app.models import UserSettings
from app.models.enums import ScheduledItemStatus, TaskStatus
from app.models.scheduled_item import ScheduledItem

logger = logging.getLogger(__name__)

_EVENTS_TTL = 600  # 10 分钟


class ScheduledItemService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str = "Asia/Shanghai",
        description: str | None = None,
        location: str | None = None,
        source: str = "manual",
        source_task_id: str | None = None,
        remind_before_minutes: int | None = None,
        status: str = "active",
    ) -> ScheduledItem:
        item = ScheduledItem(
            user_id=user_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            description=description,
            location=location,
            source=source,
            source_task_id=source_task_id,
            remind_before_minutes=remind_before_minutes,
            status=status,
        )
        self.db.add(item)
        self.db.flush()
        invalidate_user_events(user_id)
        logger.info(
            "创建日程 user_id=%s title=%s item_id=%s start=%s end=%s",
            user_id,
            title,
            item.id,
            start_time.isoformat(),
            end_time.isoformat(),
        )
        return item

    def get(self, user_id: str, item_id: str) -> ScheduledItem | None:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.id == item_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        )
        return self.db.scalar(stmt)

    def list_by_date_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        status: str | None = None,
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time < end_time,
            ScheduledItem.end_time > start_time,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if status:
            conditions.append(ScheduledItem.status == status)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def list_by_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        timezone_name = _get_user_timezone_name(self.db, user_id)
        _, _, start_utc, end_utc = _get_day_bounds(plan_date, timezone_name)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start_utc,
            ScheduledItem.start_time < end_utc,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def list_by_date_cached(self, user_id: str, plan_date: date) -> list[dict]:
        timezone_name = _get_user_timezone_name(self.db, user_id)
        cache_key = (
            f"schedule:user:{user_id}:events:date:{plan_date.isoformat()}:"
            f"tz:{timezone_name}"
        )
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items = self.list_by_date(user_id, plan_date)
        result = [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "start_time": item.start_time.isoformat(),
                "end_time": item.end_time.isoformat(),
                "timezone": item.timezone,
                "location": item.location,
                "source": item.source,
                "source_task_id": item.source_task_id,
                "remind_before_minutes": item.remind_before_minutes,
                "status": item.status,
                "sort_order": item.sort_order,
            }
            for item in items
        ]
        cache_set(cache_key, result, _EVENTS_TTL)
        return result

    def update(
        self,
        item: ScheduledItem,
        title: str | None = None,
        description: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        timezone: str | None = None,
        location: str | None = None,
        remind_before_minutes: int | None = None,
        status: str | None = None,
    ) -> ScheduledItem:
        if title is not None:
            item.title = title
        if description is not None:
            item.description = description
        if start_time is not None:
            item.start_time = start_time
        if end_time is not None:
            item.end_time = end_time
        if timezone is not None:
            item.timezone = timezone
        if location is not None:
            item.location = location
        if remind_before_minutes is not None:
            item.remind_before_minutes = remind_before_minutes
        if status is not None:
            item.status = status
        self.db.flush()
        invalidate_user_events(item.user_id)
        logger.info("更新日程 user_id=%s item_id=%s", item.user_id, item.id)
        return item

    def mark_completed(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.COMPLETED.value
        self.db.flush()
        invalidate_user_events(item.user_id)
        logger.info("完成日程 user_id=%s item_id=%s", item.user_id, item.id)
        return item

    def soft_delete(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.DELETED.value
        self.db.flush()
        invalidate_user_events(item.user_id)
        logger.info("删除日程 user_id=%s item_id=%s", item.user_id, item.id)
        return item

    def search(
        self, user_id: str, keyword: str, on_date: date | None = None
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.title.ilike(f"%{keyword}%"),
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if on_date:
            timezone_name = _get_user_timezone_name(self.db, user_id)
            _, _, start_utc, end_utc = _get_day_bounds(on_date, timezone_name)
            conditions.append(ScheduledItem.start_time >= start_utc)
            conditions.append(ScheduledItem.start_time < end_utc)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        timezone_name = _get_user_timezone_name(self.db, user_id)
        _, _, start_utc, end_utc = _get_day_bounds(plan_date, timezone_name)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start_utc,
            ScheduledItem.start_time < end_utc,
            ScheduledItem.status == ScheduledItemStatus.DRAFT.value,
        )
        items = list(self.db.scalars(stmt))
        for item in items:
            item.status = ScheduledItemStatus.ACTIVE.value
        self.db.flush()
        invalidate_user_events(user_id)
        logger.info(
            "确认草稿 user_id=%s date=%s count=%d",
            user_id,
            plan_date.isoformat(),
            len(items),
        )
        return items

    def list_pending_tasks(self, user_id: str) -> list:
        from app.models.schedule import TaskItem

        stmt = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status == TaskStatus.PENDING.value,
        ).order_by(TaskItem.priority.desc(), TaskItem.deadline.asc().nulls_last())
        return list(self.db.scalars(stmt))

    def list_by_task_id(
        self, user_id: str, task_id: str
    ) -> list[ScheduledItem]:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def generate_day_drafts(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        timezone_name = _get_user_timezone_name(self.db, user_id)
        _, _, start_utc, end_utc = _get_day_bounds(plan_date, timezone_name)
        existing = self.list_by_date_range(user_id, start_utc, end_utc)
        planned_task_ids = {
            si.source_task_id for si in existing if si.source_task_id
        }

        pending_tasks = [
            t for t in self.list_pending_tasks(user_id)
            if t.id not in planned_task_ids
        ]

        if not pending_tasks:
            return []

        base = _local_datetime(plan_date, 9, 0, timezone_name).astimezone(UTC)
        created: list[ScheduledItem] = []
        for task in pending_tasks:
            mins = task.estimated_minutes or 60
            slot_start = base
            slot_end = slot_start + timedelta(minutes=mins)

            conflict = False
            for ex in existing:
                if ex.start_time < slot_end and ex.end_time > slot_start:
                    conflict = True
                    base = ex.end_time
                    break
            if conflict:
                continue
            item = self.create(
                user_id=user_id,
                title=task.title,
                start_time=slot_start,
                end_time=slot_end,
                source="plan",
                source_task_id=task.id,
                status="draft",
            )
            created.append(item)
            base = slot_end

        logger.info(
            "生成草稿 user_id=%s date=%s count=%d",
            user_id,
            plan_date.isoformat(),
            len(created),
        )
        return created


def _get_user_timezone_name(db: Session, user_id: str) -> str:
    settings = db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    tz_name = (
        settings.default_timezone
        if settings and settings.default_timezone
        else "Asia/Shanghai"
    )
    try:
        ZoneInfo(tz_name)
    except Exception:
        return "Asia/Shanghai"
    return tz_name


def _get_day_bounds(
    plan_date: date,
    timezone_name: str,
) -> tuple[datetime, datetime, datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    start_local = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local, end_local, start_local.astimezone(UTC), end_local.astimezone(UTC)


def _local_datetime(plan_date: date, hour: int, minute: int, timezone_name: str) -> datetime:
    tz = ZoneInfo(timezone_name)
    return datetime(plan_date.year, plan_date.month, plan_date.day, hour, minute, tzinfo=tz)
