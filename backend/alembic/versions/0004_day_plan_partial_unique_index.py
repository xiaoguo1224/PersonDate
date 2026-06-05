"""allow archived day plans to coexist on the same date

Revision ID: 0004_dayplan_partial_uq
Revises: 0003_wechat_channel_schema
Create Date: 2026-06-05 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_dayplan_partial_uq"
down_revision = "0003_wechat_channel_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_day_plan_active", "day_plans", type_="unique")
    op.create_index(
        "uq_day_plan_active",
        "day_plans",
        ["user_id", "plan_date", "status"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'confirmed', 'active')"),
        sqlite_where=sa.text("status IN ('draft', 'confirmed', 'active')"),
    )


def downgrade() -> None:
    op.drop_index("uq_day_plan_active", table_name="day_plans")
    op.create_unique_constraint(
        "uq_day_plan_active",
        "day_plans",
        ["user_id", "plan_date", "status"],
    )
