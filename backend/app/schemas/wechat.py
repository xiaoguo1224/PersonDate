from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WechatLoginSessionItem(BaseModel):
    id: str
    owner_user_id: str
    login_session_id: str
    qr_payload: str
    status: str
    expires_at: datetime
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WechatLoginSessionCreateResponse(BaseModel):
    login_session_id: str
    qr_payload: str
    qr_img_content: str | None = None  # 新增
    expires_at: datetime
    status: str


class WechatLoginSessionConfirmRequest(BaseModel):
    account_id: str
    wechat_user_id: str | None = None
    bot_token: str
    base_url: str
    remark: str | None = None


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
    account_id: str | None = None
    message_id: str | None = None
    conversation_id: str
    channel_user_id: str | None = None
    direction: str
    content_type: str
    content: str | None = None
    context_token: str | None = None
    raw_payload: dict[str, Any] | None = None
    status: str
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime


class ChannelMessageLogListResponse(BaseModel):
    items: list[ChannelMessageLogItem]


class WechatAccountItem(BaseModel):
    id: str
    owner_user_id: str
    account_id: str
    wechat_user_id: str | None = None
    base_url: str
    cursor: str | None = None
    remark: str | None = None
    status: str
    bind_time: datetime | None = None
    last_active_time: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WechatAccountListResponse(BaseModel):
    items: list[WechatAccountItem]


class WechatStatusResponse(BaseModel):
    connected: bool
    channel_token_configured: bool
    total_accounts: int = 0
    active_accounts: int = 0
    queued_outbound_messages: int = 0
    sent_outbound_messages: int = 0
    failed_outbound_messages: int = 0
    total_identities: int
    active_identities: int
    bound_users: int
    last_message_at: datetime | None = None
    recent_inbound_messages: list[ChannelMessageLogItem]
    recent_outbound_messages: list[ChannelMessageLogItem]


class WechatInboundRequest(BaseModel):
    message_id: str | None = None
    account_id: str | None = None
    conversation_id: str
    channel_user_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    context_token: str | None = None
    content_type: str = "text"
    content: str
    raw_payload: dict[str, Any] | None = None


class WechatInboundResponse(BaseModel):
    handled: bool
    reply: str


class WechatSendTextRequest(BaseModel):
    conversation_id: str
    content: str


class WechatSendTextResponse(BaseModel):
    sent: bool
    conversation_id: str
    content: str
    message_id: str | None = None
    status: str | None = None
    error_message: str | None = None


class WechatOutboundQueueItem(BaseModel):
    id: str
    account_id: str
    message_id: str
    to_user_id: str
    conversation_id: str
    content: str
    context_token: str | None = None
    raw_payload: dict[str, Any] | None = None
    status: str
    retry_count: int
    error_code: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WechatOutboundQueueListResponse(BaseModel):
    items: list[WechatOutboundQueueItem]


class NotificationSettingsUpdateRequest(BaseModel):
    daily_plan_push_enabled: bool = False
    daily_plan_push_time: str = "08:00"
    city: str | None = None
