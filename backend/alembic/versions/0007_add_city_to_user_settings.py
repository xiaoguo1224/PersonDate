"""add city to user_settings

Revision ID: 0007_add_city_to_user_settings
Revises: 0006_add_qr_fields_to_login_sessions
Create Date: 2026-06-06 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_add_city_to_user_settings"
down_revision = "0006_add_qr_fields_to_login_sessions"
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
    if not _column_exists("user_settings", "city"):
        op.add_column(
            "user_settings",
            sa.Column("city", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("user_settings", "city")
