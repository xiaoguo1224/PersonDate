from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ScheduledItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_time: datetime
    end_time: datetime
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    location: str | None = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=32)
    source_task_id: str | None = None
    remind_before_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class ScheduledItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    status: str | None = Field(default=None, max_length=32)


class ScheduledItemDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    timezone: str
    location: str | None = None
    source: str
    source_task_id: str | None = None
    remind_before_minutes: int | None = None
    status: str
    sort_order: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScheduledItemListResponse(BaseModel):
    items: list[ScheduledItemDTO]


class GenerateDayDraftsRequest(BaseModel):
    include_pending_tasks: bool = True
    auto_detect_conflicts: bool = True


class ConfirmDayDraftsRequest(BaseModel):
    plan_date: date
