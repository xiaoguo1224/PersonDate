from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field


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
    messages: list[WechatChannelMessageItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("msgs", "messages"),
    )
    next_cursor: str | None = Field(
        default=None,
        validation_alias=AliasChoices("get_updates_buf", "cursor"),
    )
    error_code: str | None = None
    error_message: str | None = None


class WechatSendTextResponse(BaseModel):
    success: bool = True
    message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    detail: str | None = None
