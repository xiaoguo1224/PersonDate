from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PendingStateStatus

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


class AgentPendingState(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_pending_states"
    __table_args__ = (
        Index("ix_pending_state_user_conversation_status", "user_id", "conversation_id", "status"),
        Index("ix_pending_state_expires_at", "expires_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    state_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state_payload: Mapped[dict[str, Any]] = mapped_column(json_type, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PendingStateStatus.ACTIVE.value
    )
