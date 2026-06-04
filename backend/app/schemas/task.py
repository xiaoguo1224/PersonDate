from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    deadline: datetime | None = None
    priority: str = Field(default="medium", max_length=32)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    deadline: datetime | None = None
    priority: str | None = Field(default=None, max_length=32)


class TaskItemDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str
    status: str


class TaskListResponse(BaseModel):
    items: list[TaskItemDTO]
