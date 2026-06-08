"""add wechat channel tables and message account id

Revision ID: 0003_wechat_channel_schema
Revises: 0002_enrich_wechat_message_logs
Create Date: 2026-06-05 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_wechat_channel_schema"
down_revision = "0002_enrich_wechat_message_logs"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(index_name: str, table_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def _unique_constraint_exists(constraint_name: str, table_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    constraints = [constraint["name"] for constraint in inspector.get_unique_constraints(table_name)]
    return constraint_name in constraints


def upgrade() -> None:
    if not _table_exists("wechat_accounts"):
        op.create_table(
            "wechat_accounts",
            sa.Column("owner_user_id", sa.String(length=36), nullable=False),
            sa.Column("account_id", sa.String(length=255), nullable=False),
            sa.Column("wechat_user_id", sa.String(length=255), nullable=True),
            sa.Column("bot_token", sa.Text(), nullable=False),
            sa.Column("base_url", sa.String(length=512), nullable=False),
            sa.Column("cursor", sa.Text(), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("bind_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_active_time", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "id",
                sa.String(length=36),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["owner_user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("account_id", name="uq_wechat_accounts_account_id"),
        )
    if not _index_exists("ix_wechat_accounts_owner_user_id", "wechat_accounts"):
        op.create_index(
            "ix_wechat_accounts_owner_user_id",
            "wechat_accounts",
            ["owner_user_id"],
            unique=False,
        )
    if not _index_exists("ix_wechat_accounts_status", "wechat_accounts"):
        op.create_index(
            "ix_wechat_accounts_status",
            "wechat_accounts",
            ["status"],
            unique=False,
        )
    if not _index_exists("ix_wechat_accounts_last_active_time", "wechat_accounts"):
        op.create_index(
            "ix_wechat_accounts_last_active_time",
            "wechat_accounts",
            ["last_active_time"],
            unique=False,
        )

    if not _table_exists("wechat_login_sessions"):
        op.create_table(
            "wechat_login_sessions",
            sa.Column("owner_user_id", sa.String(length=36), nullable=False),
            sa.Column("login_session_id", sa.String(length=255), nullable=False),
            sa.Column("qr_payload", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "id",
                sa.String(length=36),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["owner_user_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint("login_session_id", name="uq_wechat_login_sessions_login_session_id"),
        )
    if not _index_exists("ix_wechat_login_sessions_owner_user_id", "wechat_login_sessions"):
        op.create_index(
            "ix_wechat_login_sessions_owner_user_id",
            "wechat_login_sessions",
            ["owner_user_id"],
            unique=False,
        )
    if not _index_exists("ix_wechat_login_sessions_status", "wechat_login_sessions"):
        op.create_index(
            "ix_wechat_login_sessions_status",
            "wechat_login_sessions",
            ["status"],
            unique=False,
        )
    if not _index_exists("ix_wechat_login_sessions_expires_at", "wechat_login_sessions"):
        op.create_index(
            "ix_wechat_login_sessions_expires_at",
            "wechat_login_sessions",
            ["expires_at"],
            unique=False,
        )

    if not _table_exists("wechat_channel_inbound_messages"):
        op.create_table(
            "wechat_channel_inbound_messages",
            sa.Column("account_id", sa.String(length=255), nullable=False),
            sa.Column("message_id", sa.String(length=255), nullable=False),
            sa.Column("cursor_token", sa.String(length=64), nullable=False),
            sa.Column("conversation_id", sa.String(length=255), nullable=False),
            sa.Column("channel_user_id", sa.String(length=255), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=True),
            sa.Column("content_type", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("context_token", sa.Text(), nullable=True),
            sa.Column("raw_payload", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "id",
                sa.String(length=36),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("account_id", "message_id", name="uq_wechat_channel_inbound_message"),
        )
    if not _index_exists("ix_wechat_channel_inbound_messages_account_id", "wechat_channel_inbound_messages"):
        op.create_index(
            "ix_wechat_channel_inbound_messages_account_id",
            "wechat_channel_inbound_messages",
            ["account_id"],
            unique=False,
        )
    if not _index_exists("ix_wechat_channel_inbound_messages_cursor_token", "wechat_channel_inbound_messages"):
        op.create_index(
            "ix_wechat_channel_inbound_messages_cursor_token",
            "wechat_channel_inbound_messages",
            ["cursor_token"],
            unique=True,
        )
    if not _index_exists("ix_wechat_channel_inbound_messages_conversation_id", "wechat_channel_inbound_messages"):
        op.create_index(
            "ix_wechat_channel_inbound_messages_conversation_id",
            "wechat_channel_inbound_messages",
            ["conversation_id"],
            unique=False,
        )
    if not _index_exists("ix_wechat_channel_inbound_messages_channel_user_id", "wechat_channel_inbound_messages"):
        op.create_index(
            "ix_wechat_channel_inbound_messages_channel_user_id",
            "wechat_channel_inbound_messages",
            ["channel_user_id"],
            unique=False,
        )
    if not _index_exists("ix_wechat_channel_inbound_messages_status", "wechat_channel_inbound_messages"):
        op.create_index(
            "ix_wechat_channel_inbound_messages_status",
            "wechat_channel_inbound_messages",
            ["status"],
            unique=False,
        )

    if not _column_exists("channel_message_logs", "account_id"):
        op.add_column(
            "channel_message_logs",
            sa.Column("account_id", sa.String(length=255), nullable=True),
        )
    if not _index_exists("ix_channel_message_logs_account_id", "channel_message_logs"):
        op.create_index(
            "ix_channel_message_logs_account_id",
            "channel_message_logs",
            ["account_id"],
            unique=False,
        )
    if not _unique_constraint_exists("uq_channel_account_message", "channel_message_logs"):
        op.create_unique_constraint(
            "uq_channel_account_message",
            "channel_message_logs",
            ["channel", "account_id", "message_id"],
        )


def downgrade() -> None:
    op.drop_constraint(
        "uq_channel_account_message",
        "channel_message_logs",
        type_="unique",
    )
    op.drop_index("ix_channel_message_logs_account_id", table_name="channel_message_logs")
    op.drop_column("channel_message_logs", "account_id")

    op.drop_index(
        "ix_wechat_login_sessions_expires_at",
        table_name="wechat_login_sessions",
    )
    op.drop_index(
        "ix_wechat_login_sessions_status",
        table_name="wechat_login_sessions",
    )
    op.drop_index(
        "ix_wechat_login_sessions_owner_user_id",
        table_name="wechat_login_sessions",
    )
    op.drop_table("wechat_login_sessions")

    op.drop_index(
        "ix_wechat_channel_inbound_messages_status",
        table_name="wechat_channel_inbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_inbound_messages_channel_user_id",
        table_name="wechat_channel_inbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_inbound_messages_conversation_id",
        table_name="wechat_channel_inbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_inbound_messages_cursor_token",
        table_name="wechat_channel_inbound_messages",
    )
    op.drop_index(
        "ix_wechat_channel_inbound_messages_account_id",
        table_name="wechat_channel_inbound_messages",
    )
    op.drop_table("wechat_channel_inbound_messages")

    op.drop_index(
        "ix_wechat_accounts_last_active_time",
        table_name="wechat_accounts",
    )
    op.drop_index("ix_wechat_accounts_status", table_name="wechat_accounts")
    op.drop_index(
        "ix_wechat_accounts_owner_user_id",
        table_name="wechat_accounts",
    )
    op.drop_table("wechat_accounts")
