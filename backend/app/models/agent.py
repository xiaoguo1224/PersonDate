from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin

json_type = JSON().with_variant(JSONB, "postgresql")


class AgentRunLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_run_logs"
    __table_args__ = (Index("ix_agent_run_logs_user_created_at", "user_id", "created_at"),)

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="wechat")
    conversation_id: Mapped[str | None] = mapped_column(String(255))
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(128))
    graph_trace: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    tools_called: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    tool_args: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    tool_results: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    final_response: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
