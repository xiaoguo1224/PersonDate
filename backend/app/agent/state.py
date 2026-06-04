from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    user_id: str
    conversation_id: str
    channel: str = "wechat"
    input_text: str
    current_time: datetime
    timezone: str = "Asia/Shanghai"

    user_settings: dict[str, Any] | None = None
    pending_state: dict[str, Any] | None = None
    intent: str | None = None
    extracted: dict[str, Any] | None = None
    candidate_events: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    free_slots: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    draft_plan: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    final_response: str | None = None
    success: bool = False
    error: str | None = None
