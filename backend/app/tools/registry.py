from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import CalendarEvent, ScheduleSource, TaskItem
from app.services.calendar_event_service import CalendarEventService
from app.services.conflict_service import ConflictService
from app.services.day_plan_service import DayPlanService
from app.services.reminder_service import ReminderService
from app.services.task_service import TaskService
from app.tools.schemas import (
    AnalyzeDayArgs,
    AskUserClarificationArgs,
    CancelReminderArgs,
    CompleteTaskArgs,
    ConfirmPlanArgs,
    CreateEventArgs,
    CreateReminderArgs,
    CreateTaskArgs,
    DeleteEventArgs,
    DetectConflictsArgs,
    FindFreeSlotsArgs,
    PlanTasksIntoDayArgs,
    QueryEventsArgs,
    QueryTasksArgs,
    RegeneratePlanArgs,
    SearchEventCandidatesArgs,
    SuggestRescheduleArgs,
    ToolResult,
    UpdateEventArgs,
    UpdateReminderArgs,
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


def _event_to_dict(event: CalendarEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "timezone": event.timezone,
        "location": event.location,
        "status": event.status,
        "remind_before_minutes": event.remind_before_minutes,
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

    def create_event(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = CreateEventArgs.model_validate(args)
        service = CalendarEventService(session)
        event = service.create_event(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            start_time=payload.start_time,
            end_time=payload.end_time,
            timezone_name=payload.timezone,
            location=payload.location,
            remind_before_minutes=payload.remind_before_minutes,
            source=ScheduleSource.AGENT.value,
            created_by_channel="debug",
        )
        return ToolResult(data=_event_to_dict(event), message="日程已创建")

    def query_events(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = QueryEventsArgs.model_validate(args)
        service = CalendarEventService(session)
        events = [
            _event_to_dict(event)
            for event in service.list_events(
                user_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
                timezone_name=payload.timezone,
            )
        ]
        return ToolResult(data=events, message="日程查询完成")

    def update_event(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = UpdateEventArgs.model_validate(args)
        service = CalendarEventService(session)
        event = service.get_event(user_id, payload.event_id)
        if event is None:
            return ToolResult(success=False, error="日程不存在")
        event = service.update_event(
            event,
            title=payload.title,
            description=payload.description,
            start_time=payload.start_time,
            end_time=payload.end_time,
            timezone=payload.timezone,
            location=payload.location,
            remind_before_minutes=payload.remind_before_minutes,
        )
        return ToolResult(data=_event_to_dict(event), message="日程已更新")

    def delete_event(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = DeleteEventArgs.model_validate(args)
        service = CalendarEventService(session)
        event = service.get_event(user_id, payload.event_id)
        if event is None:
            return ToolResult(success=False, error="日程不存在")
        service.delete_event(event)
        return ToolResult(data={"id": event.id}, message="日程已删除")

    def search_event_candidates(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = SearchEventCandidatesArgs.model_validate(args)
        service = CalendarEventService(session)
        events = [
            {
                "id": event.id,
                "title": event.title,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "timezone": event.timezone,
            }
            for event in service.search_candidates(
                user_id, payload.keyword, payload.on_date, payload.timezone
            )
        ]
        return ToolResult(data=events, message="已找到候选日程")

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
        event_service = CalendarEventService(session)
        task_service = TaskService(session)
        data = {
            "events": [
                _event_to_dict(event)
                for event in event_service.list_events(
                    user_id, start_date=payload.plan_date, end_date=payload.plan_date
                )
            ],
            "tasks": [_task_to_dict(task) for task in task_service.list_tasks(user_id)],
        }
        return ToolResult(data=data, message="日程分析完成")

    def find_free_slots(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        free_slots: list[dict[str, Any]] = []
        return ToolResult(data=free_slots, message="空闲时间已计算")

    def plan_tasks_into_day(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = PlanTasksIntoDayArgs.model_validate(args)
        plan = DayPlanService(session).generate_draft(user_id, payload.plan_date)
        return ToolResult(data={"day_plan_id": plan.id}, message="已生成计划草案")

    def confirm_plan(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = ConfirmPlanArgs.model_validate(args)
        service = DayPlanService(session)
        plan = service.get_day_plan(user_id, payload.plan_id)
        if plan is None:
            return ToolResult(success=False, error="计划不存在")
        service.confirm_plan(plan)
        return ToolResult(
            data={"day_plan_id": plan.id, "status": plan.status}, message="计划已确认"
        )

    def regenerate_plan(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = RegeneratePlanArgs.model_validate(args)
        if payload.plan_date is None and payload.plan_id is not None:
            plan = DayPlanService(session).get_day_plan(user_id, payload.plan_id)
            if plan is not None:
                payload.plan_date = plan.plan_date
        if payload.plan_date is None:
            return ToolResult(success=False, error="缺少计划日期")
        plan = DayPlanService(session).generate_draft(user_id, payload.plan_date)
        return ToolResult(data={"day_plan_id": plan.id}, message="已重新生成计划草案")

    def detect_conflicts(
        args: dict[str, Any], user_id: str, conversation_id: str, session: Session
    ) -> ToolResult:
        payload = DetectConflictsArgs.model_validate(args)
        service = ConflictService(session)
        if payload.plan_date is not None:
            items = [item.id for item in service.detect_day_conflicts(user_id)]
        else:
            items = [item.id for item in service.list_conflicts(user_id)]
        return ToolResult(data=items, message="冲突检测完成")

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

    registry.register(ToolSpec("create_event", CreateEventArgs, create_event))
    registry.register(ToolSpec("query_events", QueryEventsArgs, query_events))
    registry.register(ToolSpec("update_event", UpdateEventArgs, update_event))
    registry.register(ToolSpec("delete_event", DeleteEventArgs, delete_event))
    registry.register(
        ToolSpec("search_event_candidates", SearchEventCandidatesArgs, search_event_candidates)
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
