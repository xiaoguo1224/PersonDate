from pydantic import BaseModel, Field


class DebugMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class DebugMessageResponse(BaseModel):
    success: bool
    final_response: str | None = None
    intent: str | None = None
    tool_calls: list[dict] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list)
    pending_state: dict | None = None
    graph_trace: list[str] = Field(default_factory=list)
    error: str | None = None
