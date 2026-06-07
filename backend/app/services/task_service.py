from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScheduleSource, TaskItem, TaskStatus
from app.models.enums import ScheduledItemStatus
from app.models.scheduled_item import ScheduledItem


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
    ) -> TaskItem:
        item = TaskItem(
            user_id=user_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            deadline=deadline,
            priority=priority,
            source=source,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def list_tasks(self, user_id: str, status: str | None = None) -> list[TaskItem]:
        stmt = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status != TaskStatus.DELETED.value,
        )
        if status:
            stmt = stmt.where(TaskItem.status == status)
        return list(self.db.scalars(stmt.order_by(TaskItem.created_at.desc())))

    def get_task(self, user_id: str, task_id: str) -> TaskItem | None:
        stmt = select(TaskItem).where(TaskItem.user_id == user_id, TaskItem.id == task_id)
        return self.db.scalar(stmt)

    def update_task(self, task: TaskItem, **changes: object) -> TaskItem:
        for key, value in changes.items():
            if value is not None:
                setattr(task, key, value)
        return task

    def complete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.COMPLETED.value
        # 标记该任务关联的所有安排项为已完成
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.COMPLETED.value
        return task

    def delete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.DELETED.value
        # 软删除该任务关联的所有安排项
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.DELETED.value
        return task
