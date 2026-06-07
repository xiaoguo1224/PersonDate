from datetime import date, datetime, time

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    deadline: datetime | None = None
    priority: str = Field(default="medium", max_length=32)
    schedule_type: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    time_type: str | None = Field(default=None, max_length=32)
    scheduled_time: time | None = None
    scheduled_end_time: time | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    deadline: datetime | None = None
    priority: str | None = Field(default=None, max_length=32)
    schedule_type: str | None = Field(default=None, max_length=32)
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1)
    time_type: str | None = Field(default=None, max_length=32)
    scheduled_time: time | None = None
    scheduled_end_time: time | None = None


class TaskItemDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str
    status: str
    schedule_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    time_type: str | None = None
    scheduled_time: time | None = None
    scheduled_end_time: time | None = None
    completed_days: int = 0


class TaskListResponse(BaseModel):
    items: list[TaskItemDTO]
