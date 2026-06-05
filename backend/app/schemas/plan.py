from datetime import date, datetime

from pydantic import BaseModel, Field


class DayPlanGenerateRequest(BaseModel):
    include_pending_tasks: bool = True
    auto_detect_conflicts: bool = True


class DayPlanConfirmResponse(BaseModel):
    id: str
    plan_date: date
    status: str


class PlanItemCreateRequest(BaseModel):
    plan_date: date
    title: str = Field(min_length=1, max_length=255)
    item_type: str = Field(default="manual", max_length=32)
    start_time: datetime
    end_time: datetime
    status: str = Field(default="planned", max_length=32)
    is_flexible: bool = False
    sort_order: int = 0
    ref_id: str | None = Field(default=None, max_length=36)


class PlanItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    item_type: str | None = Field(default=None, max_length=32)
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str | None = Field(default=None, max_length=32)
    is_flexible: bool | None = None
    sort_order: int | None = None
    ref_id: str | None = Field(default=None, max_length=36)


class PlanItemDTO(BaseModel):
    id: str
    day_plan_id: str
    title: str
    item_type: str
    start_time: datetime
    end_time: datetime
    status: str
    is_flexible: bool
    sort_order: int | None = None
    ref_id: str | None = None


class DayPlanDTO(BaseModel):
    id: str
    plan_date: date
    summary: str | None = None
    status: str
    items: list[PlanItemDTO] = Field(default_factory=list)
