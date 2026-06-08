"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-04 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

jsonb_type = JSON().with_variant(JSONB, "postgresql")
uuid_default = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("default_timezone", sa.String(length=64), nullable=False),
        sa.Column("workday_start_time", sa.String(length=8), nullable=True),
        sa.Column("workday_end_time", sa.String(length=8), nullable=True),
        sa.Column("daily_plan_push_time", sa.String(length=8), nullable=True),
        sa.Column("default_remind_before_minutes", sa.Integer(), nullable=True),
        sa.Column("daily_plan_push_enabled", sa.Boolean(), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "invite_codes",
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "invite_code_usages",
        sa.Column("invite_code_id", sa.String(length=36), sa.ForeignKey("invite_codes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "channel_identities",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("channel_user_id", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("channel", "channel_user_id", name="uq_channel_user"),
        sa.UniqueConstraint("channel", "conversation_id", name="uq_channel_conversation"),
    )

    op.create_table(
        "wechat_binding_codes",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "wechat_accounts",
        sa.Column("owner_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("wechat_user_id", sa.String(length=255), nullable=True),
        sa.Column("bot_token", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("bind_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wechat_accounts_owner_user_id", "wechat_accounts", ["owner_user_id"])
    op.create_index("ix_wechat_accounts_status", "wechat_accounts", ["status"])
    op.create_index("ix_wechat_accounts_last_active_time", "wechat_accounts", ["last_active_time"])

    op.create_table(
        "wechat_login_sessions",
        sa.Column("owner_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("login_session_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("qr_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qr_img_content", sa.Text(), nullable=True),
        sa.Column("qrcode_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_wechat_login_sessions_owner_user_id", "wechat_login_sessions", ["owner_user_id"])
    op.create_index("ix_wechat_login_sessions_status", "wechat_login_sessions", ["status"])
    op.create_index("ix_wechat_login_sessions_expires_at", "wechat_login_sessions", ["expires_at"])

    op.create_table(
        "channel_message_logs",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("channel_user_id", sa.String(length=255), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("context_token", sa.Text(), nullable=True),
        sa.Column("raw_payload", jsonb_type, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("account_id", sa.String(length=255), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("channel", "account_id", "message_id", name="uq_channel_account_message"),
    )
    op.create_index("ix_channel_message_logs_account_id", "channel_message_logs", ["account_id"])
    op.create_index(
        "ix_message_logs_conversation_dir_time",
        "channel_message_logs",
        ["conversation_id", "direction", "created_at"],
    )

    op.create_table(
        "task_items",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("schedule_type", sa.String(length=32), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("time_type", sa.String(length=32), nullable=True),
        sa.Column("scheduled_time", sa.Time(), nullable=True),
        sa.Column("scheduled_end_time", sa.Time(), nullable=True),
        sa.Column("completed_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_items_user_status", "task_items", ["user_id", "status"])

    op.create_table(
        "schedule_conflicts",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conflict_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("related_item_ids", jsonb_type, nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conflicts_user_status", "schedule_conflicts", ["user_id", "status"])
    op.create_index("ix_conflicts_user_type", "schedule_conflicts", ["user_id", "conflict_type"])

    op.create_table(
        "reminder_jobs",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("trigger_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reminders_user_status", "reminder_jobs", ["user_id", "status"])
    op.create_index("ix_reminders_trigger_time", "reminder_jobs", ["trigger_time"])

    op.create_table(
        "agent_run_logs",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=True),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=128), nullable=True),
        sa.Column("graph_trace", jsonb_type, nullable=True),
        sa.Column("tools_called", jsonb_type, nullable=True),
        sa.Column("tool_args", jsonb_type, nullable=True),
        sa.Column("tool_results", jsonb_type, nullable=True),
        sa.Column("final_response", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_run_logs_user_created_at", "agent_run_logs", ["user_id", "created_at"])

    op.create_table(
        "agent_pending_states",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("state_type", sa.String(length=64), nullable=False),
        sa.Column("state_payload", jsonb_type, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pending_state_user_conversation_status",
        "agent_pending_states",
        ["user_id", "conversation_id", "status"],
    )
    op.create_index("ix_pending_state_expires_at", "agent_pending_states", ["expires_at"])

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("value", jsonb_type, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "scheduled_items",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Asia/Shanghai'::character varying")),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'manual'::character varying")),
        sa.Column("source_task_id", sa.String(length=36), sa.ForeignKey("task_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("remind_before_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'::character varying")),
        sa.Column("sort_order", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduled_items_user_time", "scheduled_items", ["user_id", "start_time"])
    op.create_index("ix_scheduled_items_user_status", "scheduled_items", ["user_id", "status"])
    op.create_index("ix_scheduled_items_source_task", "scheduled_items", ["source_task_id"])
    op.create_index("ix_scheduled_items_user_start", "scheduled_items", ["user_id", "start_time"])

    op.create_table(
        "wechat_channel_inbound_messages",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("account_id", sa.String(length=255), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("cursor_token", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=255), nullable=False),
        sa.Column("channel_user_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default=sa.text("'text'::character varying")),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("context_token", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'::character varying")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("account_id", "message_id", name="uq_wechat_channel_inbound_message"),
    )
    op.create_index("ix_wechat_channel_inbound_messages_account_id", "wechat_channel_inbound_messages", ["account_id"])
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
    op.create_index("ix_wechat_channel_inbound_messages_status", "wechat_channel_inbound_messages", ["status"])

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
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True, server_default=uuid_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "message_id", name="uq_wechat_channel_outbound_message"),
    )
    op.create_index("ix_wechat_channel_outbound_messages_account_id", "wechat_channel_outbound_messages", ["account_id"])
    op.create_index("ix_wechat_channel_outbound_messages_to_user_id", "wechat_channel_outbound_messages", ["to_user_id"])
    op.create_index("ix_wechat_channel_outbound_messages_conversation_id", "wechat_channel_outbound_messages", ["conversation_id"])
    op.create_index("ix_wechat_channel_outbound_messages_status", "wechat_channel_outbound_messages", ["status"])
    op.create_index("ix_wechat_channel_outbound_messages_sent_at", "wechat_channel_outbound_messages", ["sent_at"])


def downgrade() -> None:
    op.drop_table("wechat_channel_outbound_messages")
    op.drop_table("wechat_channel_inbound_messages")
    op.drop_index("ix_scheduled_items_user_start", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_source_task", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_user_status", table_name="scheduled_items")
    op.drop_index("ix_scheduled_items_user_time", table_name="scheduled_items")
    op.drop_table("scheduled_items")
    op.drop_table("system_settings")
    op.drop_index("ix_pending_state_expires_at", table_name="agent_pending_states")
    op.drop_index("ix_pending_state_user_conversation_status", table_name="agent_pending_states")
    op.drop_table("agent_pending_states")
    op.drop_index("ix_agent_run_logs_user_created_at", table_name="agent_run_logs")
    op.drop_table("agent_run_logs")
    op.drop_index("ix_reminders_trigger_time", table_name="reminder_jobs")
    op.drop_index("ix_reminders_user_status", table_name="reminder_jobs")
    op.drop_table("reminder_jobs")
    op.drop_index("ix_conflicts_user_type", table_name="schedule_conflicts")
    op.drop_index("ix_conflicts_user_status", table_name="schedule_conflicts")
    op.drop_table("schedule_conflicts")
    op.drop_index("ix_task_items_user_status", table_name="task_items")
    op.drop_table("task_items")
    op.drop_index("ix_message_logs_conversation_dir_time", table_name="channel_message_logs")
    op.drop_index("ix_channel_message_logs_account_id", table_name="channel_message_logs")
    op.drop_table("channel_message_logs")
    op.drop_index("ix_wechat_login_sessions_expires_at", table_name="wechat_login_sessions")
    op.drop_index("ix_wechat_login_sessions_status", table_name="wechat_login_sessions")
    op.drop_index("ix_wechat_login_sessions_owner_user_id", table_name="wechat_login_sessions")
    op.drop_table("wechat_login_sessions")
    op.drop_index("ix_wechat_accounts_last_active_time", table_name="wechat_accounts")
    op.drop_index("ix_wechat_accounts_status", table_name="wechat_accounts")
    op.drop_index("ix_wechat_accounts_owner_user_id", table_name="wechat_accounts")
    op.drop_table("wechat_accounts")
    op.drop_table("wechat_binding_codes")
    op.drop_table("channel_identities")
    op.drop_table("invite_code_usages")
    op.drop_table("invite_codes")
    op.drop_table("user_settings")
    op.drop_table("users")
