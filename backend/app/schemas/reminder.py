from datetime import datetime

from pydantic import BaseModel


class ReminderDTO(BaseModel):
    id: str
    target_type: str
    target_id: str
    title: str
    conversation_id: str
    trigger_time: datetime
    status: str
    retry_count: int
    max_retries: int
    error_message: str | None = None
    fired_at: datetime | None = None


class ReminderListResponse(BaseModel):
    items: list[ReminderDTO]
    total: int
    page: int
    page_size: int
