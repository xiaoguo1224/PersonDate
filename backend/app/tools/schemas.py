from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool = True
    data: Any | None = None
    message: str | None = None
    error: str | None = None


class CreateScheduledItemArgs(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=0, ge=0)


class QueryScheduledItemsArgs(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    keyword: str | None = None
    on_date: date | None = None
    timezone: str = "Asia/Shanghai"


class UpdateScheduledItemArgs(BaseModel):
    item_id: str
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    timezone: str | None = None
    location: str | None = None
    remind_before_minutes: int | None = None


class DeleteScheduledItemArgs(BaseModel):
    item_id: str


class CreateTaskArgs(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str = Field(default="medium", max_length=32)
    schedule_type: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    time_type: str | None = Field(default=None, max_length=32)
    scheduled_time: str | None = None
    scheduled_end_time: str | None = None


class QueryTasksArgs(BaseModel):
    status: str | None = None


class UpdateTaskArgs(BaseModel):
    task_id: str
    title: str | None = None
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str | None = None
    schedule_type: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    time_type: str | None = Field(default=None, max_length=32)
    scheduled_time: str | None = None
    scheduled_end_time: str | None = None


class CompleteTaskArgs(BaseModel):
    task_id: str


class DeleteTaskArgs(BaseModel):
    task_id: str


class AnalyzeDayArgs(BaseModel):
    plan_date: date


class FindFreeSlotsArgs(BaseModel):
    plan_date: date


class PlanTasksIntoDayArgs(BaseModel):
    plan_date: date


class ConfirmPlanArgs(BaseModel):
    plan_date: date


class RegeneratePlanArgs(BaseModel):
    plan_id: str | None = None
    plan_date: date | None = None
    feedback: str | None = None


class DetectConflictsArgs(BaseModel):
    plan_date: date | None = None


class SuggestRescheduleArgs(BaseModel):
    conflict_id: str


class CreateReminderArgs(BaseModel):
    target_type: str
    target_id: str
    title: str
    trigger_time: datetime
    conversation_id: str | None = None


class UpdateReminderArgs(BaseModel):
    reminder_id: str
    title: str | None = None
    trigger_time: datetime | None = None


class CancelReminderArgs(BaseModel):
    reminder_id: str


class AskUserClarificationArgs(BaseModel):
    prompt: str
    reason: str | None = None
