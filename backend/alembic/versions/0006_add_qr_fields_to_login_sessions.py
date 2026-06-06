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


def upgrade() -> None:
    op.add_column(
        "wechat_login_sessions",
        sa.Column("qr_img_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "wechat_login_sessions",
        sa.Column("qrcode_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wechat_login_sessions", "qrcode_id")
    op.drop_column("wechat_login_sessions", "qr_img_content")
