"""add wechat channel outbound messages

Revision ID: 0005_wechat_channel_outbound_messages
Revises: 0004_dayplan_partial_uq
Create Date: 2026-06-06 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_wechat_channel_outbound_messages"
down_revision = "0004_dayplan_partial_uq"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    if not _table_exists("wechat_channel_outbound_messages"):
        op.create_table(
            "wechat_channel_outbound_messages",
        sa.Column("account_id", sa.String(length=255), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("to_user_id", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_token", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            sa.String(length=36),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "message_id", name="uq_wechat_channel_outbound_message"),
    )
    op.create_index(
        "ix_wechat_channel_outbound_messages_account_id",
        "wechat_channel_outbound_messages",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_wechat_channel_outbound_messages_to_user_id",
        "wechat_channel_outbound_messages",
        ["to_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_wechat_channel_outbound_messages_conversation_id",
        "wechat_channel_outbound_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_wechat_channel_outbound_messages_status",
        "wechat_channel_outbound_messages",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_wechat_channel_outbound_messages_sent_at",
        "wechat_channel_outbound_messages",
        ["sent_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wechat_channel_outbound_messages_sent_at",
        table_name="wechat_channel_outbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_outbound_messages_status",
        table_name="wechat_channel_outbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_outbound_messages_conversation_id",
        table_name="wechat_channel_outbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_outbound_messages_to_user_id",
        table_name="wechat_channel_outbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_outbound_messages_account_id",
        table_name="wechat_channel_outbound_messages",
    )
    op.drop_table("wechat_channel_outbound_messages")
