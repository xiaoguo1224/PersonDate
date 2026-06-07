from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConflictDTO(BaseModel):
    id: str
    conflict_type: str
    severity: str
    title: str
    description: str | None = None
    related_item_ids: dict[str, Any] | None = None
    suggestion: str | None = None
    status: str
    detected_at: datetime


class ConflictListResponse(BaseModel):
    items: list[ConflictDTO]
    total: int
    page: int
    page_size: int
