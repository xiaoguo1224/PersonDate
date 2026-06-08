"""task_enhancement_fields

Revision ID: 5cf529c74989
Revises: 0009_scheduled_items_unification
Create Date: 2026-06-07 15:26:51.650987

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5cf529c74989'
down_revision = '0009_scheduled_items_unification'
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
    if not _column_exists('task_items', 'schedule_type'):
        op.add_column('task_items', sa.Column('schedule_type', sa.String(32), nullable=True, server_default=None))
    if not _column_exists('task_items', 'start_date'):
        op.add_column('task_items', sa.Column('start_date', sa.Date, nullable=True))
    if not _column_exists('task_items', 'end_date'):
        op.add_column('task_items', sa.Column('end_date', sa.Date, nullable=True))
    if not _column_exists('task_items', 'duration_days'):
        op.add_column('task_items', sa.Column('duration_days', sa.Integer, nullable=True))
    if not _column_exists('task_items', 'time_type'):
        op.add_column('task_items', sa.Column('time_type', sa.String(32), nullable=True, server_default=None))
    if not _column_exists('task_items', 'scheduled_time'):
        op.add_column('task_items', sa.Column('scheduled_time', sa.Time, nullable=True))
    if not _column_exists('task_items', 'scheduled_end_time'):
        op.add_column('task_items', sa.Column('scheduled_end_time', sa.Time, nullable=True))
    if not _column_exists('task_items', 'completed_days'):
        op.add_column('task_items', sa.Column('completed_days', sa.Integer, nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('task_items', 'completed_days')
    op.drop_column('task_items', 'scheduled_end_time')
    op.drop_column('task_items', 'scheduled_time')
    op.drop_column('task_items', 'time_type')
    op.drop_column('task_items', 'duration_days')
    op.drop_column('task_items', 'end_date')
    op.drop_column('task_items', 'start_date')
    op.drop_column('task_items', 'schedule_type')
