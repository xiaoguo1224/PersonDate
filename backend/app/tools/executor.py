from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.tools.registry import ToolRegistry, build_default_tool_registry
from app.tools.schemas import ToolResult


class ToolExecutor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.registry: ToolRegistry = build_default_tool_registry(db)

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user_id: str,
        conversation_id: str,
    ) -> ToolResult:
        spec = self.registry.get(tool_name)
        validated = spec.schema.model_validate(arguments)
        result = spec.handler(validated.model_dump(), user_id, conversation_id, self.db)
        self.db.flush()
        return result
