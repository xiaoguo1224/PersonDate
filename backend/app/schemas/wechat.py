from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WechatBindingCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class ChannelIdentityItem(BaseModel):
    id: str
    user_id: str
    channel: str
    channel_user_id: str
    conversation_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    status: str
    bound_at: datetime | None = None
    created_at: datetime


class ChannelIdentityListResponse(BaseModel):
    items: list[ChannelIdentityItem]


class ChannelMessageLogItem(BaseModel):
    id: str
    user_id: str | None = None
    channel: str
    message_id: str | None = None
    conversation_id: str
    channel_user_id: str | None = None
    direction: str
    content_type: str
    content: str | None = None
    raw_payload: dict[str, Any] | None = None
    status: str
    error_message: str | None = None
    created_at: datetime


class ChannelMessageLogListResponse(BaseModel):
    items: list[ChannelMessageLogItem]


class WechatStatusResponse(BaseModel):
    connected: bool
    channel_token_configured: bool
    total_identities: int
    active_identities: int
    bound_users: int
    last_message_at: datetime | None = None
    recent_inbound_messages: list[ChannelMessageLogItem]
    recent_outbound_messages: list[ChannelMessageLogItem]


class WechatInboundRequest(BaseModel):
    message_id: str | None = None
    conversation_id: str
    channel_user_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    content_type: str = "text"
    content: str
    raw_payload: dict[str, Any] | None = None


class WechatInboundResponse(BaseModel):
    handled: bool
    reply: str
