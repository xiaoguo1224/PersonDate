from datetime import datetime

from pydantic import BaseModel, Field


class InviteCodeCreateRequest(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_at: datetime | None = None
    remark: str | None = Field(default=None, max_length=500)


class InviteCodeItem(BaseModel):
    id: str
    code: str
    max_uses: int
    used_count: int
    expires_at: datetime | None = None
    status: str
    remark: str | None = None


class InviteCodeListResponse(BaseModel):
    items: list[InviteCodeItem]
