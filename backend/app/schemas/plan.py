from datetime import date, datetime

from pydantic import BaseModel, Field


class DayPlanGenerateRequest(BaseModel):
    include_pending_tasks: bool = True
    auto_detect_conflicts: bool = True


class DayPlanConfirmResponse(BaseModel):
    id: str
    plan_date: date
    status: str


class PlanItemDTO(BaseModel):
    id: str
    title: str
    item_type: str
    start_time: datetime
    end_time: datetime
    status: str


class DayPlanDTO(BaseModel):
    id: str
    plan_date: date
    summary: str | None = None
    status: str
    items: list[PlanItemDTO] = Field(default_factory=list)
