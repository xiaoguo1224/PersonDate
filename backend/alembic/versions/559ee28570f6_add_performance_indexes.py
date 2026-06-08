"""add_performance_indexes

Revision ID: 559ee28570f6
Revises: 5cf529c74989
Create Date: 2026-06-08 05:37:15.910266

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '559ee28570f6'
down_revision = '5cf529c74989'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_message_logs_conversation_dir_time', 'channel_message_logs', ['conversation_id', 'direction', 'created_at'], unique=False)
    op.create_index('ix_scheduled_items_user_start', 'scheduled_items', ['user_id', 'start_time'], unique=False)
    op.create_index('ix_task_items_user_status', 'task_items', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_task_items_user_status', table_name='task_items')
    op.drop_index('ix_scheduled_items_user_start', table_name='scheduled_items')
    op.drop_index('ix_message_logs_conversation_dir_time', table_name='channel_message_logs')
