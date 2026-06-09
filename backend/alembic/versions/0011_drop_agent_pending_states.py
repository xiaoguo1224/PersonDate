"""drop agent_pending_states table

Revision ID: 0011_drop_agent_pending_states
Revises: 0010_reminder_conversation_id_nullable
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_drop_agent_pending_states"
down_revision = "0010_reminder_conversation_id_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("agent_pending_states")


def downgrade() -> None:
    op.create_table(
        "agent_pending_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("state_type", sa.String(64), nullable=False),
        sa.Column("state_payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pending_state_user_conversation_status", "agent_pending_states", ["user_id", "conversation_id", "status"])
    op.create_index("ix_pending_state_expires_at", "agent_pending_states", ["expires_at"])
