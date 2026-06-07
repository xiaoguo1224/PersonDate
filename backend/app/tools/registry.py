from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import TaskItem
from app.models.enums import ReminderTargetType
from app.services.conflict_service import ConflictService
from app.services.reminder_service import ReminderService
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService
from app.tools.schemas import (
    AnalyzeDayArgs,
    AskUserClarificationArgs,
    CancelReminderArgs,
    CompleteTaskArgs,
    ConfirmPlanArgs,
    CreateReminderArgs,
    CreateScheduledItemArgs,
    CreateTaskArgs,
    DeleteScheduledItemArgs,
    DetectConflictsArgs,
    FindFreeSlotsArgs,
    PlanTasksIntoDayArgs,
    QueryScheduledItemsArgs,
    QueryTasksArgs,
    RegeneratePlanArgs,
    SuggestRescheduleArgs,
    ToolResult,
    UpdateReminderArgs,
    UpdateScheduledItemArgs,
    UpdateTaskArgs,
)


@dataclass(slots=True)
class ToolSpec:
    name: str
    schema: type[Any]
    handler: Callable[[dict[str, Any], str, str, Session], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"未知工具: {name}")
        return self._tools[name]

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)


def _item_to_dict(item: object) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "start_time": item.start_time,
        "end_time": item.end_time,
        "timezone": item.timezone,
        "location": item.location,
        "status": item.status,
        "remind_before_minutes": item.remind_before_minutes,
    }


def _task_to_dict(task: TaskItem) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "estimated_minutes": task.estimated_minutes,
        "deadline": task.deadline,
        "priority": task.priority,
        "status": task.status,
    }


def build_default_tool_registry(db: Session) -> ToolRegistry:
    registry = ToolRegistry()

    def create_scheduled_item(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CreateScheduledItemArgs.model_validate(args)
        service = ScheduledItemService(session)
        end_time = payload.end_time or payload.start_time

        if payload.end_time is None:
            end_time = payload.start_time + timedelta(hours=1)
        item = service.create(
            user_id=user_id,
            title=payload.title,
            start_time=payload.start_time,
            end_time=end_time,
            timezone=payload.timezone,
            location=payload.location,
            remind_before_minutes=payload.remind_before_minutes,
            source="agent",
        )
        # 创建提醒
        remind_before = payload.remind_before_minutes or 0
        trigger_time = payload.start_time - timedelta(minutes=remind_before)
        ReminderService(session).create_for_target(
            user_id=user_id,
            target_type=ReminderTargetType.SCHEDULED_ITEM.value,
            target_id=item.id,
            title=item.title,
            trigger_time=trigger_time,
            conversation_id=conversation_id,
        )
        # 检测冲突
        ConflictService(session).detect_item_conflicts(user_id, item)
        session.commit()
        return ToolResult(data=_item_to_dict(item), message="安排已创建")

    def query_scheduled_items(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = QueryScheduledItemsArgs.model_validate(args)
        service = ScheduledItemService(session)

        if payload.keyword:
            items = service.search(user_id, payload.keyword, payload.on_date)
        elif payload.start_date and payload.end_date:
            from datetime import datetime as dt

            start = dt.combine(payload.start_date, dt.min.time())
            end = dt.combine(payload.end_date, dt.max.time())
            items = service.list_by_date_range(user_id, start_time=start, end_time=end)
        else:
            items = []
        return ToolResult(data=[_item_to_dict(item) for item in items], message="安排查询完成")

    def update_scheduled_item(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = UpdateScheduledItemArgs.model_validate(args)
        service = ScheduledItemService(session)
        item = service.get(user_id, payload.item_id)
        if item is None:
            return ToolResult(success=False, error="安排不存在")
        item = service.update(
            item,
            title=payload.title,
            description=payload.description,
            start_time=payload.start_time,
            end_time=payload.end_time,
            timezone=payload.timezone,
            location=payload.location,
            remind_before_minutes=payload.remind_before_minutes,
        )
        # 更新提醒时间
        if payload.start_time is not None:
            remind_before = payload.remind_before_minutes if payload.remind_before_minutes is not None else (item.remind_before_minutes or 0)
            ReminderService(session).cancel_by_target(user_id=user_id, target_id=item.id)
            ReminderService(session).create_for_target(
                user_id=user_id,
                target_type=ReminderTargetType.SCHEDULED_ITEM.value,
                target_id=item.id,
                title=item.title,
                trigger_time=payload.start_time - timedelta(minutes=remind_before),
                conversation_id=conversation_id,
            )
        return ToolResult(data=_item_to_dict(item), message="安排已更新")

    def delete_scheduled_item(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = DeleteScheduledItemArgs.model_validate(args)
        service = ScheduledItemService(session)
        item = service.get(user_id, payload.item_id)
        if item is None:
            return ToolResult(success=False, error="安排不存在")
        service.soft_delete(item)
        return ToolResult(data={"id": item.id}, message="安排已删除")

    def create_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CreateTaskArgs.model_validate(args)
        task = TaskService(session).create_task(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            estimated_minutes=payload.estimated_minutes,
            deadline=payload.deadline,
            priority=payload.priority,
        )
        return ToolResult(data=_task_to_dict(task), message="任务已创建")

    def query_tasks(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = QueryTasksArgs.model_validate(args)
        tasks = [
            _task_to_dict(task) for task in TaskService(session).list_tasks(user_id, payload.status)
        ]
        return ToolResult(data=tasks, message="任务查询完成")

    def update_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = UpdateTaskArgs.model_validate(args)
        service = TaskService(session)
        task = service.get_task(user_id, payload.task_id)
        if task is None:
            return ToolResult(success=False, error="任务不存在")
        task = service.update_task(
            task,
            title=payload.title,
            description=payload.description,
            estimated_minutes=payload.estimated_minutes,
            deadline=payload.deadline,
            priority=payload.priority,
        )
        return ToolResult(data=_task_to_dict(task), message="任务已更新")

    def complete_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CompleteTaskArgs.model_validate(args)
        service = TaskService(session)
        task = service.get_task(user_id, payload.task_id)
        if task is None:
            return ToolResult(success=False, error="任务不存在")
        service.complete_task(task)
        return ToolResult(data=_task_to_dict(task), message="任务已完成")

    def analyze_day(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = AnalyzeDayArgs.model_validate(args)
        item_service = ScheduledItemService(session)
        task_service = TaskService(session)
        items = item_service.list_by_date(user_id, payload.plan_date)
        data = {
            "items": [_item_to_dict(item) for item in items],
            "tasks": [_task_to_dict(task) for task in task_service.list_tasks(user_id)],
        }
        return ToolResult(data=data, message="安排分析完成")

    def find_free_slots(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        free_slots: list[dict[str, Any]] = []
        return ToolResult(data=free_slots, message="空闲时间已计算")

    def plan_tasks_into_day(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = PlanTasksIntoDayArgs.model_validate(args)
        service = ScheduledItemService(session)
        items = service.generate_day_drafts(user_id, payload.plan_date)
        session.commit()
        return ToolResult(data=[_item_to_dict(item) for item in items], message="已生成安排草案")

    def confirm_plan(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = ConfirmPlanArgs.model_validate(args)
        service = ScheduledItemService(session)
        count = service.confirm_drafts_for_date(user_id, payload.plan_date)
        session.commit()
        return ToolResult(data={"confirmed_count": count}, message="安排已确认")

    def regenerate_plan(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = RegeneratePlanArgs.model_validate(args)
        if payload.plan_date is None:
            return ToolResult(success=False, error="缺少日期")
        service = ScheduledItemService(session)
        # 先删除当日所有 draft 安排，再重新生成
        existing = service.list_by_date(user_id, payload.plan_date)
        for item in existing:
            if item.status == "draft":
                service.soft_delete(item)
        items = service.generate_day_drafts(user_id, payload.plan_date)
        session.commit()
        return ToolResult(
            data=[_item_to_dict(item) for item in items],
            message="已重新生成安排草案",
        )

    def detect_conflicts(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = DetectConflictsArgs.model_validate(args)
        service = ConflictService(session)
        if payload.plan_date is not None:
            conflicts = service.detect_day_conflicts(user_id)
        else:
            conflicts = service.list_conflicts(user_id)
        return ToolResult(data=[c.id for c in conflicts], message="冲突检测完成")

    def suggest_reschedule(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        return ToolResult(data=args, message="建议稍后补充")

    def create_reminder(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CreateReminderArgs.model_validate(args)
        job = ReminderService(session).create_for_target(
            user_id=user_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            title=payload.title,
            trigger_time=payload.trigger_time,
            conversation_id=payload.conversation_id or conversation_id,
        )
        return ToolResult(data={"id": job.id}, message="提醒已创建")

    def update_reminder(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = UpdateReminderArgs.model_validate(args)
        service = ReminderService(session)
        job = service.get_job(user_id, payload.reminder_id)
        if job is None:
            return ToolResult(success=False, error="提醒不存在")
        if payload.title is not None:
            job.title = payload.title
        if payload.trigger_time is not None:
            job.trigger_time = payload.trigger_time
        return ToolResult(data={"id": job.id}, message="提醒已更新")

    def cancel_reminder(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CancelReminderArgs.model_validate(args)
        service = ReminderService(session)
        job = service.get_job(user_id, payload.reminder_id)
        if job is None:
            return ToolResult(success=False, error="提醒不存在")
        service.cancel_job(job)
        return ToolResult(data={"id": job.id}, message="提醒已取消")

    def ask_user_clarification(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = AskUserClarificationArgs.model_validate(args)
        return ToolResult(data={"prompt": payload.prompt}, message=payload.reason or payload.prompt)

    registry.register(
        ToolSpec("create_scheduled_item", CreateScheduledItemArgs, create_scheduled_item)
    )
    registry.register(
        ToolSpec("query_scheduled_items", QueryScheduledItemsArgs, query_scheduled_items)
    )
    registry.register(
        ToolSpec("update_scheduled_item", UpdateScheduledItemArgs, update_scheduled_item)
    )
    registry.register(
        ToolSpec("delete_scheduled_item", DeleteScheduledItemArgs, delete_scheduled_item)
    )
    registry.register(ToolSpec("create_task", CreateTaskArgs, create_task))
    registry.register(ToolSpec("query_tasks", QueryTasksArgs, query_tasks))
    registry.register(ToolSpec("update_task", UpdateTaskArgs, update_task))
    registry.register(ToolSpec("complete_task", CompleteTaskArgs, complete_task))
    registry.register(ToolSpec("analyze_day", AnalyzeDayArgs, analyze_day))
    registry.register(ToolSpec("find_free_slots", FindFreeSlotsArgs, find_free_slots))
    registry.register(ToolSpec("plan_tasks_into_day", PlanTasksIntoDayArgs, plan_tasks_into_day))
    registry.register(ToolSpec("confirm_plan", ConfirmPlanArgs, confirm_plan))
    registry.register(ToolSpec("regenerate_plan", RegeneratePlanArgs, regenerate_plan))
    registry.register(ToolSpec("detect_conflicts", DetectConflictsArgs, detect_conflicts))
    registry.register(ToolSpec("suggest_reschedule", SuggestRescheduleArgs, suggest_reschedule))
    registry.register(ToolSpec("create_reminder", CreateReminderArgs, create_reminder))
    registry.register(ToolSpec("update_reminder", UpdateReminderArgs, update_reminder))
    registry.register(ToolSpec("cancel_reminder", CancelReminderArgs, cancel_reminder))
    registry.register(
        ToolSpec("ask_user_clarification", AskUserClarificationArgs, ask_user_clarification)
    )
    return registry
