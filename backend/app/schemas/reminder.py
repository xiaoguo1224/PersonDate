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


class ReminderListResponse(BaseModel):
    items: list[ReminderDTO]
