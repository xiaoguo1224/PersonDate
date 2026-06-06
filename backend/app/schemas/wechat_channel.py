from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator


class WechatGetUpdatesRequest(BaseModel):
    bot_token: str | None = None
    account_id: str | None = None
    get_updates_buf: str | None = None


class WechatSendMessageRequest(BaseModel):
    to_user_id: str
    content: str
    conversation_id: str | None = None
    account_id: str | None = None
    context_token: str | None = None


class WechatGetConfigRequest(BaseModel):
    account_id: str | None = None
    bot_token: str | None = None


class WechatSendTypingRequest(BaseModel):
    conversation_id: str
    typing: bool = True
    account_id: str | None = None
    bot_token: str | None = None
    typing_ticket: str | None = None


class WechatChannelMessageItem(BaseModel):
    message_id: str | None = None
    from_user_id: str | None = None
    to_user_id: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    channel_user_id: str | None = None
    display_name: str | None = None
    content_type: str = "text"
    content: str | None = None
    context_token: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WechatGetUpdatesResponse(BaseModel):
    success: bool = True
    ret: int = 0
    messages: list[WechatChannelMessageItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("msgs", "messages"),
    )
    next_cursor: str | None = Field(
        default=None,
        validation_alias=AliasChoices("next_cursor", "get_updates_buf", "cursor"),
    )
    error_code: str | None = None
    error_message: str | None = None
    longpolling_timeout_ms: int | None = None


class WechatSendTextResponse(BaseModel):
    success: bool = True
    ret: int = 0
    status: str | None = None
    message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    detail: str | None = None


class WechatGetConfigResponse(BaseModel):
    success: bool = True
    ret: int = 0
    account_id: str | None = None
    status: str | None = None
    cursor: str | None = None
    remark: str | None = None
    typing_ticket: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class WechatSendTypingResponse(BaseModel):
    success: bool = True
    ret: int = 0
    typing: bool = True
    error_code: str | None = None
    error_message: str | None = None


class WechatGetUploadUrlRequest(BaseModel):
    filekey: str
    media_type: int
    to_user_id: str
    rawsize: int
    rawfilemd5: str
    filesize: int
    thumb_rawsize: int | None = None
    thumb_rawfilemd5: str | None = None
    thumb_filesize: int | None = None

    @model_validator(mode="after")
    def validate_thumb_fields(self) -> WechatGetUploadUrlRequest:
        if self.media_type in (1, 2):
            if (
                self.thumb_rawsize is None
                or self.thumb_rawfilemd5 is None
                or self.thumb_filesize is None
            ):
                raise ValueError("图片和视频上传必须提供缩略图参数")
        return self


class WechatGetUploadUrlResponse(BaseModel):
    success: bool = True
    ret: int = 0
    upload_param: str | None = None
    thumb_upload_param: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class WechatChannelOutboundMessageItem(BaseModel):
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


class WechatChannelOutboundMessageListResponse(BaseModel):
    items: list[WechatChannelOutboundMessageItem]


class WechatIngestMessageRequest(BaseModel):
    account_id: str
    message_id: str | None = None
    conversation_id: str
    channel_user_id: str
    display_name: str | None = None
    content_type: str = "text"
    content: str
    context_token: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WechatIngestMessageResponse(BaseModel):
    success: bool = True
    ret: int = 0
    account_id: str
    message_id: str
    cursor_token: str
    status: str = "queued"
    deduplicated: bool = False
    error_code: str | None = None
    error_message: str | None = None


class WechatChannelInboundMessageItem(BaseModel):
    id: str
    account_id: str
    message_id: str
    cursor_token: str
    conversation_id: str
    channel_user_id: str
    display_name: str | None = None
    content_type: str = "text"
    content: str | None = None
    context_token: str | None = None
    raw_payload: dict[str, Any] | None = None
    status: str
    delivered_at: datetime | None = None
    created_at: datetime


class WechatChannelInboundMessageListResponse(BaseModel):
    items: list[WechatChannelInboundMessageItem]
