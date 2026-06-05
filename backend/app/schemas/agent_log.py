from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentLogItem(BaseModel):
    id: str
    user_id: str | None = None
    channel: str
    conversation_id: str | None = None
    input_text: str
    intent: str | None = None
    graph_trace: list[str] | None = None
    tools_called: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None
    final_response: str | None = None
    success: bool
    error_message: str | None = None
    created_at: datetime


class AgentLogListResponse(BaseModel):
    items: list[AgentLogItem]
