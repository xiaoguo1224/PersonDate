from datetime import datetime

from pydantic import BaseModel


class UserAdminItem(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    status: str
    default_timezone: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class UserAdminListResponse(BaseModel):
    items: list[UserAdminItem]


class ChannelIdentityAdminItem(BaseModel):
    id: str
    channel: str
    channel_user_id: str
    conversation_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    status: str
    bound_at: datetime | None = None
    created_at: datetime


class ChannelIdentityAdminListResponse(BaseModel):
    items: list[ChannelIdentityAdminItem]
