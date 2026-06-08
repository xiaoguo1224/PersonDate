"""add_performance_indexes

Revision ID: 559ee28570f6
Revises: 5cf529c74989
Create Date: 2026-06-08 05:37:15.910266

"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '559ee28570f6'
down_revision = '5cf529c74989'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(index_name: str, table_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [idx["name"] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    if not _index_exists('ix_message_logs_conversation_dir_time', 'channel_message_logs'):
        op.create_index('ix_message_logs_conversation_dir_time', 'channel_message_logs', ['conversation_id', 'direction', 'created_at'], unique=False)
    if not _index_exists('ix_scheduled_items_user_start', 'scheduled_items'):
        op.create_index('ix_scheduled_items_user_start', 'scheduled_items', ['user_id', 'start_time'], unique=False)
    if not _index_exists('ix_task_items_user_status', 'task_items'):
        op.create_index('ix_task_items_user_status', 'task_items', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_task_items_user_status', table_name='task_items')
    op.drop_index('ix_scheduled_items_user_start', table_name='scheduled_items')
    op.drop_index('ix_message_logs_conversation_dir_time', table_name='channel_message_logs')
