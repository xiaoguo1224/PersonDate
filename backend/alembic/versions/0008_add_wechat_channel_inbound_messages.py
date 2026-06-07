"""add wechat_channel_inbound_messages table

Revision ID: 0008_add_wechat_channel_inbound_messages
Revises: 0007_add_city_to_user_settings
Create Date: 2026-06-06 15:35:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_add_wechat_channel_inbound_messages"
down_revision: str | None = "0007_add_city_to_user_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wechat_channel_inbound_messages",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("cursor_token", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("channel_user_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("context_token", sa.Text, nullable=True),
        sa.Column("raw_payload", sa.JSON, nullable=True, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "message_id", name="uq_wechat_channel_inbound_message"),
    )
    op.create_index(
        "ix_wechat_channel_inbound_messages_account_id",
        "wechat_channel_inbound_messages",
        ["account_id"],
    )
    op.create_index(
        "ix_wechat_channel_inbound_messages_cursor_token",
        "wechat_channel_inbound_messages",
        ["cursor_token"],
        unique=True,
    )
    op.create_index(
        "ix_wechat_channel_inbound_messages_conversation_id",
        "wechat_channel_inbound_messages",
        ["conversation_id"],
    )
    op.create_index(
        "ix_wechat_channel_inbound_messages_channel_user_id",
        "wechat_channel_inbound_messages",
        ["channel_user_id"],
    )
    op.create_index(
        "ix_wechat_channel_inbound_messages_status",
        "wechat_channel_inbound_messages",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_wechat_channel_inbound_messages_status")
    op.drop_index("ix_wechat_channel_inbound_messages_channel_user_id")
    op.drop_index("ix_wechat_channel_inbound_messages_conversation_id")
    op.drop_index("ix_wechat_channel_inbound_messages_cursor_token")
    op.drop_index("ix_wechat_channel_inbound_messages_account_id")
    op.drop_table("wechat_channel_inbound_messages")
