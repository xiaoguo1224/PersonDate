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


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("city", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "city")
