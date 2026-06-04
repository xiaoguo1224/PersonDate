from datetime import datetime

from pydantic import BaseModel, Field


class CalendarEventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=0, ge=0, le=24 * 60)


class CalendarEventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class CalendarEventItem(BaseModel):
    id: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    timezone: str
    location: str | None = None
    status: str
    remind_before_minutes: int | None = None


class CalendarEventListResponse(BaseModel):
    items: list[CalendarEventItem]


class SearchEventCandidatesRequest(BaseModel):
    keyword: str
    date: str | None = None


class SearchEventCandidateItem(BaseModel):
    id: str
    title: str
    start_time: datetime
    end_time: datetime | None = None
    timezone: str


class SearchEventCandidatesResponse(BaseModel):
    items: list[SearchEventCandidateItem]
