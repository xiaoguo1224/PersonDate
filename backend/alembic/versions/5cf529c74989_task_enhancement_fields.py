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


def upgrade() -> None:
    op.add_column('task_items', sa.Column('schedule_type', sa.String(32), nullable=True, server_default=None))
    op.add_column('task_items', sa.Column('start_date', sa.Date, nullable=True))
    op.add_column('task_items', sa.Column('end_date', sa.Date, nullable=True))
    op.add_column('task_items', sa.Column('duration_days', sa.Integer, nullable=True))
    op.add_column('task_items', sa.Column('time_type', sa.String(32), nullable=True, server_default=None))
    op.add_column('task_items', sa.Column('scheduled_time', sa.Time, nullable=True))
    op.add_column('task_items', sa.Column('scheduled_end_time', sa.Time, nullable=True))
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
