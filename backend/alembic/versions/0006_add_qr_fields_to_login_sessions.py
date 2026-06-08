"""add qr_img_content and qrcode_id to login_sessions

Revision ID: 0006_add_qr_fields_to_login_sessions
Revises: 0005_wechat_channel_outbound_messages
Create Date: 2026-06-06 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_add_qr_fields_to_login_sessions"
down_revision = "0005_wechat_channel_outbound_messages"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _column_exists("wechat_login_sessions", "qr_img_content"):
        op.add_column(
            "wechat_login_sessions",
            sa.Column("qr_img_content", sa.Text(), nullable=True),
        )
    if not _column_exists("wechat_login_sessions", "qrcode_id"):
        op.add_column(
            "wechat_login_sessions",
            sa.Column("qrcode_id", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("wechat_login_sessions", "qrcode_id")
    op.drop_column("wechat_login_sessions", "qr_img_content")
