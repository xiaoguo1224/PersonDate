from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_tasks
from app.models import ScheduleSource, TaskItem, TaskStatus
from app.models.enums import ScheduledItemStatus, ScheduledItemSource, TaskScheduleType, TaskTimeType
from app.models.scheduled_item import ScheduledItem


_TASKS_TTL = 600  # 10 分钟
_UNSET = object()


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(
        self,
        *,
        user_id: str,
        title: str,
        description: str | None = None,
        estimated_minutes: int | None = None,
        deadline: datetime | None = None,
        priority: str = "medium",
        source: str = ScheduleSource.AGENT.value,
        schedule_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        duration_days: int | None = None,
        time_type: str | None = None,
        scheduled_time: time | None = None,
        scheduled_end_time: time | None = None,
    ) -> TaskItem:
        item = TaskItem(
            user_id=user_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            deadline=deadline,
            priority=priority,
            source=source,
            schedule_type=schedule_type,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            time_type=time_type,
            scheduled_time=scheduled_time,
            scheduled_end_time=scheduled_end_time,
        )
        self.db.add(item)
        self.db.flush()
        invalidate_user_tasks(user_id)
        logger.info("创建任务 user_id=%s title=%s task_id=%s", user_id, title, item.id)
        return item

    def list_tasks(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TaskItem], int]:
        base = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status != TaskStatus.DELETED.value,
        )
        if status:
            base = base.where(TaskItem.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            base = base.where(
                (TaskItem.title.ilike(pattern)) | (TaskItem.description.ilike(pattern))
            )
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        items = list(
            self.db.scalars(
                base.order_by(TaskItem.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def list_tasks_cached(self, user_id: str, status: str | None = None) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:tasks:status:{status or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items, _ = self.list_tasks(user_id, status=status, page_size=100)
        result = [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "estimated_minutes": item.estimated_minutes,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "priority": item.priority,
                "status": item.status,
                "schedule_type": item.schedule_type,
                "start_date": item.start_date.isoformat() if item.start_date else None,
                "end_date": item.end_date.isoformat() if item.end_date else None,
                "duration_days": item.duration_days,
                "time_type": item.time_type,
                "scheduled_time": str(item.scheduled_time) if item.scheduled_time else None,
                "scheduled_end_time": str(item.scheduled_end_time) if item.scheduled_end_time else None,
                "completed_days": item.completed_days,
            }
            for item in items
        ]
        cache_set(cache_key, result, _TASKS_TTL)
        return result

    def get_task(self, user_id: str, task_id: str) -> TaskItem | None:
        stmt = select(TaskItem).where(TaskItem.user_id == user_id, TaskItem.id == task_id)
        return self.db.scalar(stmt)

    def update_task(self, task: TaskItem, **changes: object) -> TaskItem:
        applied: list[str] = []
        for key, value in changes.items():
            if value is _UNSET:
                continue
            setattr(task, key, value)
            applied.append(key)
        invalidate_user_tasks(task.user_id)
        logger.info("更新任务 user_id=%s task_id=%s 字段=%s", task.user_id, task.id, ",".join(applied))
        return task

    def complete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.COMPLETED.value
        task.completed_days = (task.completed_days or 0) + 1
        logger.info("完成任务 user_id=%s task_id=%s", task.user_id, task.id)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.COMPLETED.value
        invalidate_user_tasks(task.user_id)
        return task

    def delete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.DELETED.value
        logger.info("删除任务 user_id=%s task_id=%s", task.user_id, task.id)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.DELETED.value
        invalidate_user_tasks(task.user_id)
        return task

    def complete_task_day(self, task: TaskItem) -> TaskItem:
        task.completed_days = (task.completed_days or 0) + 1
        return task

    def get_dates_for_task(self, task: TaskItem, limit: int = 30) -> list[date]:
        if task.schedule_type == TaskScheduleType.DAILY:
            start = task.start_date or date.today()
            end = task.end_date or (task.deadline.date() if task.deadline else start + timedelta(days=limit - 1))
            return _date_range(start, end)

        if task.schedule_type == TaskScheduleType.WEEKDAYS:
            start = task.start_date or date.today()
            end = task.end_date or (task.deadline.date() if task.deadline else start + timedelta(days=limit - 1))
            return _weekday_range(start, end)

        if task.schedule_type == TaskScheduleType.DURATION_DAYS:
            start = task.start_date or date.today()
            days = task.duration_days or 1
            return _date_range(start, start + timedelta(days=days - 1))

        if task.schedule_type == TaskScheduleType.CUSTOM_RANGE:
            if task.start_date and task.end_date:
                return _date_range(task.start_date, task.end_date)

        return []

    def list_scheduled_items_for_task(
        self, user_id: str, task_id: str
    ) -> list[ScheduledItem]:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def sync_task_to_scheduled_items(
        self,
        task: TaskItem,
        user_id: str,
        timezone: str = "Asia/Shanghai",
    ) -> list[ScheduledItem]:
        from app.services.scheduled_item_service import ScheduledItemService

        si_service = ScheduledItemService(self.db)

        existing = si_service.list_by_task_id(user_id, task.id)
        for item in existing:
            if item.source != ScheduledItemSource.MANUAL.value:
                si_service.soft_delete(item)

        dates = self.get_dates_for_task(task)
        if not dates:
            return []

        mins = task.estimated_minutes or 60
        created: list[ScheduledItem] = []

        for d in dates:
            if task.time_type == TaskTimeType.FIXED and task.scheduled_time is not None:
                start_dt = _combine_local(d, task.scheduled_time, timezone)
                end_dt = (
                    _combine_local(d, task.scheduled_end_time, timezone)
                    if task.scheduled_end_time
                    else start_dt + timedelta(minutes=mins)
                )
                item = si_service.create(
                    user_id=user_id,
                    title=task.title,
                    start_time=start_dt,
                    end_time=end_dt,
                    timezone=timezone,
                    source=ScheduledItemSource.TASK.value,
                    source_task_id=task.id,
                    status=ScheduledItemStatus.ACTIVE.value,
                )
                created.append(item)
            else:
                # time_type 为 flexible 或 None 时，自动排到空闲时段
                slot = self._find_next_free_slot(user_id, d, mins, timezone)
                if slot:
                    item = si_service.create(
                        user_id=user_id,
                        title=task.title,
                        start_time=slot[0],
                        end_time=slot[1],
                        timezone=timezone,
                        source=ScheduledItemSource.TASK.value,
                        source_task_id=task.id,
                        status=ScheduledItemStatus.ACTIVE.value,
                    )
                    created.append(item)

        return created

    def reschedule_conflicted_item(
        self,
        user_id: str,
        task: TaskItem,
        item: ScheduledItem,
        timezone: str = "Asia/Shanghai",
    ) -> tuple[bool, ScheduledItem | None]:
        if task.time_type != TaskTimeType.FLEXIBLE:
            return False, None

        item_date = item.start_time.astimezone(_tzinfo(timezone)).date()
        mins = task.estimated_minutes or 60
        slot = self._find_next_free_slot(user_id, item_date, mins, timezone, exclude_id=item.id)
        if not slot:
            return False, None

        from app.services.scheduled_item_service import ScheduledItemService
        si_service = ScheduledItemService(self.db)
        updated = si_service.update(item, start_time=slot[0], end_time=slot[1])
        return True, updated

    def _find_next_free_slot(
        self,
        user_id: str,
        plan_date: date,
        duration_minutes: int,
        timezone: str = "Asia/Shanghai",
        exclude_id: str | None = None,
    ) -> tuple[datetime, datetime] | None:
        day_start = datetime(plan_date.year, plan_date.month, plan_date.day, 8, 0, tzinfo=_tzinfo(timezone))
        day_end = datetime(plan_date.year, plan_date.month, plan_date.day, 22, 0, tzinfo=_tzinfo(timezone))

        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time < day_end,
            ScheduledItem.end_time > day_start,
            ScheduledItem.status.notin_([
                ScheduledItemStatus.DELETED.value,
                ScheduledItemStatus.CANCELLED.value,
            ]),
        )
        if exclude_id:
            stmt = stmt.where(ScheduledItem.id != exclude_id)

        existing = list(self.db.scalars(stmt.order_by(ScheduledItem.start_time)))
        if not existing:
            return day_start, day_start + timedelta(minutes=duration_minutes)

        candidate = day_start
        for ex in existing:
            if candidate + timedelta(minutes=duration_minutes) <= ex.start_time:
                return candidate, candidate + timedelta(minutes=duration_minutes)
            if ex.end_time > candidate:
                candidate = ex.end_time

        if candidate + timedelta(minutes=duration_minutes) <= day_end:
            return candidate, candidate + timedelta(minutes=duration_minutes)

        return None


def _date_range(start: date, end: date) -> list[date]:
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _weekday_range(start: date, end: date) -> list[date]:
    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _combine_local(d: date, t: time, tz_name: str) -> datetime:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=tz)


def _tzinfo(tz_name: str):
    from zoneinfo import ZoneInfo
    return ZoneInfo(tz_name)
