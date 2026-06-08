from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import TaskItem
from app.models.enums import ReminderTargetType
from app.services.channel_identity_service import ChannelIdentityService
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
    DeleteTaskArgs,
    DetectConflictsArgs,
    FindFreeSlotsArgs,
    PlanTasksIntoDayArgs,
    QueryRemindersArgs,
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
        "schedule_type": task.schedule_type,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "end_date": task.end_date.isoformat() if task.end_date else None,
        "duration_days": task.duration_days,
        "time_type": task.time_type,
        "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else None,
        "scheduled_end_time": task.scheduled_end_time.isoformat() if task.scheduled_end_time else None,
        "completed_days": task.completed_days or 0,
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
        real_conversation_id = ChannelIdentityService(session).get_conversation_id(user_id)
        ReminderService(session).create_for_target(
            user_id=user_id,
            target_type=ReminderTargetType.SCHEDULED_ITEM.value,
            target_id=item.id,
            title=item.title,
            trigger_time=trigger_time,
            conversation_id=real_conversation_id,
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
        from datetime import time as dt_time
        payload = CreateTaskArgs.model_validate(args)

        sched_time = None
        sched_end_time = None
        if payload.scheduled_time:
            parts = payload.scheduled_time.split(":")
            sched_time = dt_time(int(parts[0]), int(parts[1]))
        if payload.scheduled_end_time:
            parts = payload.scheduled_end_time.split(":")
            sched_end_time = dt_time(int(parts[0]), int(parts[1]))

        task = TaskService(session).create_task(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            estimated_minutes=payload.estimated_minutes,
            deadline=payload.deadline,
            priority=payload.priority,
            schedule_type=payload.schedule_type,
            start_date=payload.start_date,
            end_date=payload.end_date,
            duration_days=payload.duration_days,
            time_type=payload.time_type,
            scheduled_time=sched_time,
            scheduled_end_time=sched_end_time,
        )

        # 自动生成 ScheduledItem
        items = []
        if task.schedule_type:
            items = TaskService(session).sync_task_to_scheduled_items(task, user_id)
        session.commit()
        msg = "任务已创建"
        if items:
            msg = f"任务已创建，已生成 {len(items)} 个排期"
        return ToolResult(data=_task_to_dict(task), message=msg)

    def query_tasks(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = QueryTasksArgs.model_validate(args)
        tasks = [
            _task_to_dict(task) for task in TaskService(session).list_tasks(user_id, payload.status)[0]
        ]
        return ToolResult(data=tasks, message="任务查询完成")

    def update_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        from datetime import time as dt_time
        from app.services.task_service import _UNSET
        payload = UpdateTaskArgs.model_validate(args)
        service = TaskService(session)
        task = service.get_task(user_id, payload.task_id)
        if task is None:
            return ToolResult(success=False, error="任务不存在")

        sched_time = _UNSET
        sched_end_time = _UNSET
        if payload.scheduled_time:
            parts = payload.scheduled_time.split(":")
            sched_time = dt_time(int(parts[0]), int(parts[1]))
        if payload.scheduled_end_time:
            parts = payload.scheduled_end_time.split(":")
            sched_end_time = dt_time(int(parts[0]), int(parts[1]))

        SCHEDULE_FIELDS = {
            "schedule_type", "start_date", "end_date",
            "duration_days", "time_type", "scheduled_time",
            "scheduled_end_time", "estimated_minutes",
        }
        schedule_changed = any(
            getattr(payload, field) is not None for field in SCHEDULE_FIELDS
        )

        task = service.update_task(
            task,
            title=payload.title,
            description=payload.description,
            estimated_minutes=payload.estimated_minutes,
            deadline=payload.deadline,
            priority=payload.priority,
            schedule_type=payload.schedule_type,
            start_date=payload.start_date,
            end_date=payload.end_date,
            duration_days=payload.duration_days,
            time_type=payload.time_type,
            scheduled_time=sched_time,
            scheduled_end_time=sched_end_time,
        )

        # 同步排期：只在排期字段变更时触发
        items = []
        if schedule_changed and task.schedule_type:
            items = service.sync_task_to_scheduled_items(task, user_id)
        elif payload.title is not None:
            si_service = ScheduledItemService(session)
            for item in si_service.list_by_task_id(user_id, task.id):
                si_service.update(item, title=task.title)

        session.commit()
        msg = "任务已更新"
        if items:
            msg = f"任务已更新，已同步 {len(items)} 个排期"
        return ToolResult(data=_task_to_dict(task), message=msg)

    def complete_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CompleteTaskArgs.model_validate(args)
        service = TaskService(session)
        task = service.get_task(user_id, payload.task_id)
        if task is None:
            return ToolResult(success=False, error="任务不存在")
        service.complete_task(task)
        session.commit()
        return ToolResult(data=_task_to_dict(task), message="任务已完成")

    def delete_task(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = DeleteTaskArgs.model_validate(args)
        service = TaskService(session)
        task = service.get_task(user_id, payload.task_id)
        if task is None:
            return ToolResult(success=False, error="任务不存在")
        service.delete_task(task)
        session.commit()
        return ToolResult(data={"id": task.id}, message="任务已删除")

    def analyze_day(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = AnalyzeDayArgs.model_validate(args)
        item_service = ScheduledItemService(session)
        task_service = TaskService(session)
        items = item_service.list_by_date(user_id, payload.plan_date)
        data = {
            "items": [_item_to_dict(item) for item in items],
            "tasks": [_task_to_dict(task) for task in task_service.list_tasks(user_id)[0]],
        }
        return ToolResult(data=data, message="安排分析完成")

    def find_free_slots(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        from datetime import UTC, datetime as dt, time as dt_time
        from zoneinfo import ZoneInfo

        payload = FindFreeSlotsArgs.model_validate(args)
        service = ScheduledItemService(session)
        items = service.list_by_date(user_id, payload.plan_date)

        user_tz = ZoneInfo(payload.timezone)
        start_parts = payload.workday_start.split(":")
        end_parts = payload.workday_end.split(":")
        day_start_local = dt(
            payload.plan_date.year, payload.plan_date.month, payload.plan_date.day,
            int(start_parts[0]), int(start_parts[1]), tzinfo=user_tz,
        )
        day_end_local = dt(
            payload.plan_date.year, payload.plan_date.month, payload.plan_date.day,
            int(end_parts[0]), int(end_parts[1]), tzinfo=user_tz,
        )
        day_start = day_start_local.astimezone(UTC)
        day_end = day_end_local.astimezone(UTC)

        active_items = sorted(
            [
                i for i in items
                if i.status == "active"
                and i.end_time.astimezone(UTC) > day_start
                and i.start_time.astimezone(UTC) < day_end
            ],
            key=lambda x: x.start_time,
        )

        free_slots: list[dict[str, Any]] = []
        cursor = day_start
        for item in active_items:
            item_start = max(item.start_time.astimezone(UTC), day_start)
            item_end = min(item.end_time.astimezone(UTC), day_end)
            if item_start > cursor:
                slot_minutes = int((item_start - cursor).total_seconds() // 60)
                free_slots.append({
                    "start_time": cursor.isoformat(),
                    "end_time": item_start.isoformat(),
                    "duration_minutes": slot_minutes,
                })
            if item_end > cursor:
                cursor = item_end
        if cursor < day_end:
            slot_minutes = int((day_end - cursor).total_seconds() // 60)
            free_slots.append({
                "start_time": cursor.isoformat(),
                "end_time": day_end.isoformat(),
                "duration_minutes": slot_minutes,
            })
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
            conflicts = service.list_conflicts(user_id)[0]
        return ToolResult(data=[c.id for c in conflicts], message="冲突检测完成")

    def suggest_reschedule(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        from datetime import UTC, datetime as dt, timedelta

        payload = SuggestRescheduleArgs.model_validate(args)
        conflict_service = ConflictService(session)
        conflict = conflict_service.get_conflict(user_id, payload.conflict_id)
        if conflict is None:
            return ToolResult(success=False, error="冲突不存在")
        if conflict.status != "open":
            return ToolResult(success=False, error="冲突已处理")

        related = conflict.related_item_ids or {}
        item_id_a = related.get("current")
        item_id_b = related.get("other")
        if not item_id_a or not item_id_b:
            return ToolResult(success=False, error="冲突缺少关联安排")

        item_service = ScheduledItemService(session)
        item_a = item_service.get(user_id, item_id_a)
        item_b = item_service.get(user_id, item_id_b)
        if item_a is None or item_b is None:
            return ToolResult(success=False, error="关联安排不存在")

        conflict_date = item_a.start_time.astimezone(UTC).date()
        free_slots_result = find_free_slots(
            {
                "plan_date": conflict_date,
                "workday_start": "09:00",
                "workday_end": "22:00",
            },
            user_id=user_id,
            conversation_id=conversation_id,
            session=session,
        )
        free_slots = free_slots_result.data or []

        suggestions: list[dict[str, Any]] = []
        for item in [item_a, item_b]:
            duration = int((item.end_time - item.start_time).total_seconds() // 60)
            for slot in free_slots:
                if slot["duration_minutes"] >= duration:
                    slot_start = dt.fromisoformat(slot["start_time"])
                    slot_end = slot_start + timedelta(minutes=duration)
                    suggestions.append({
                        "item_id": item.id,
                        "item_title": item.title,
                        "original_start": item.start_time.isoformat(),
                        "original_end": item.end_time.isoformat(),
                        "suggested_start": slot_start.isoformat(),
                        "suggested_end": slot_end.isoformat(),
                        "reason": f"将「{item.title}」移至空闲时段 {slot_start:%H:%M}-{slot_end:%H:%M}",
                    })
                    break
        return ToolResult(data={
            "conflict_id": conflict.id,
            "conflict_title": conflict.title,
            "suggestions": suggestions,
        }, message="已生成调整建议")

    def create_reminder(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CreateReminderArgs.model_validate(args)
        real_conversation_id = ChannelIdentityService(session).get_conversation_id(user_id)
        job = ReminderService(session).create_for_target(
            user_id=user_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            title=payload.title,
            trigger_time=payload.trigger_time,
            conversation_id=payload.conversation_id or real_conversation_id,
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

    def query_reminders(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = QueryRemindersArgs.model_validate(args)
        service = ReminderService(session)
        items, total = service.list_jobs(
            user_id,
            status=payload.status or "pending",
            keyword=payload.keyword,
        )
        data = [
            {
                "id": item.id,
                "title": item.title,
                "trigger_time": item.trigger_time.isoformat(),
                "status": item.status,
            }
            for item in items
        ]
        return ToolResult(data=data, message=f"提醒查询完成，共 {total} 条")

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
    registry.register(ToolSpec("delete_task", DeleteTaskArgs, delete_task))
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
    registry.register(ToolSpec("query_reminders", QueryRemindersArgs, query_reminders))
    registry.register(
        ToolSpec("ask_user_clarification", AskUserClarificationArgs, ask_user_clarification)
    )
    return registry
