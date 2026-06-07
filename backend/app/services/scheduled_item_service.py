from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import UTC

from app.models.enums import ScheduledItemStatus, TaskStatus
from app.models.scheduled_item import ScheduledItem


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
        start = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=UTC)
        end = start.replace(hour=23, minute=59, second=59)
        return self.list_by_date_range(user_id, start, end)

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
        return item

    def mark_completed(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.COMPLETED.value
        self.db.flush()
        return item

    def soft_delete(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.DELETED.value
        self.db.flush()
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
            start = datetime(on_date.year, on_date.month, on_date.day)
            end = start.replace(hour=23, minute=59, second=59)
            conditions.append(ScheduledItem.start_time >= start)
            conditions.append(ScheduledItem.start_time <= end)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> int:
        start = datetime(plan_date.year, plan_date.month, plan_date.day)
        end = start.replace(hour=23, minute=59, second=59)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start,
            ScheduledItem.start_time <= end,
            ScheduledItem.status == ScheduledItemStatus.DRAFT.value,
        )
        items = list(self.db.scalars(stmt))
        for item in items:
            item.status = ScheduledItemStatus.ACTIVE.value
        self.db.flush()
        return len(items)

    def list_pending_tasks(self, user_id: str) -> list:
        from app.models.schedule import TaskItem

        stmt = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status == TaskStatus.PENDING.value,
        ).order_by(TaskItem.priority.desc(), TaskItem.deadline.asc().nulls_last())
        return list(self.db.scalars(stmt))

    def generate_day_drafts(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        existing = self.list_by_date(user_id, plan_date)
        planned_task_ids = {
            si.source_task_id for si in existing if si.source_task_id
        }

        pending_tasks = [
            t for t in self.list_pending_tasks(user_id)
            if t.id not in planned_task_ids
        ]

        if not pending_tasks:
            return []

        base = datetime(plan_date.year, plan_date.month, plan_date.day, 9, 0, tzinfo=UTC)
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

        return created
