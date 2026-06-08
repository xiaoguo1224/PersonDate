"""enrich wechat message logs

Revision ID: 0002_enrich_wechat_message_logs
Revises: 0001_initial_schema
Create Date: 2026-06-05 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_enrich_wechat_message_logs"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("channel_message_logs", "context_token"):
        op.add_column(
            "channel_message_logs",
            sa.Column("context_token", sa.Text(), nullable=True),
        )
    if not _column_exists("channel_message_logs", "retry_count"):
        op.add_column(
            "channel_message_logs",
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if not _column_exists("channel_message_logs", "error_code"):
        op.add_column(
            "channel_message_logs",
            sa.Column("error_code", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("channel_message_logs", "error_code")
    op.drop_column("channel_message_logs", "retry_count")
    op.drop_column("channel_message_logs", "context_token")
