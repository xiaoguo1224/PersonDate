from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent.security import ToolCallGuard
from app.tools.registry import ToolRegistry, build_default_tool_registry
from app.tools.schemas import ToolResult


class ToolExecutor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.registry: ToolRegistry = build_default_tool_registry(db)
        self.guard = ToolCallGuard()

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user_id: str,
        conversation_id: str,
        confirmed_action: str | None = None,
    ) -> ToolResult:
        allowed, reason = self.guard.check_tool_call(tool_name, arguments, confirmed_action)
        if not allowed:
            return ToolResult(success=False, error=reason)

        arguments = self.guard.filter_args(tool_name, arguments)

        spec = self.registry.get(tool_name)
        validated = spec.schema.model_validate(arguments)
        result = spec.handler(validated.model_dump(), user_id, conversation_id, self.db)
        self.db.flush()
        return result
