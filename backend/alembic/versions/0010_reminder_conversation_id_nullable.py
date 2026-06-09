"""reminder_jobs conversation_id 改为可空

Revision ID: 0010_reminder_conversation_id_nullable
Revises: 0009_scheduled_items_unification
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0010_reminder_conversation_id_nullable"
down_revision: str = "559ee28570f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "reminder_jobs",
        "conversation_id",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "reminder_jobs",
        "conversation_id",
        existing_type=sa.String(255),
        nullable=False,
    )
