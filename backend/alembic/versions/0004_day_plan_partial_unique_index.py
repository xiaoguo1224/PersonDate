"""allow archived day plans to coexist on the same date

Revision ID: 0004_dayplan_partial_uq
Revises: 0003_wechat_channel_schema
Create Date: 2026-06-05 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_dayplan_partial_uq"
down_revision = "0003_wechat_channel_schema"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _constraint_exists(constraint_name: str, table_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    unique_constraints = [constraint["name"] for constraint in inspector.get_unique_constraints(table_name)]
    return constraint_name in unique_constraints


def _index_exists(index_name: str, table_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = [index["name"] for index in inspector.get_indexes(table_name)]
    return index_name in indexes


def upgrade() -> None:
    if not _table_exists("day_plans"):
        return
    if _constraint_exists("uq_day_plan_active", "day_plans"):
        op.drop_constraint("uq_day_plan_active", "day_plans", type_="unique")
    if not _index_exists("uq_day_plan_active", "day_plans"):
        op.create_index(
            "uq_day_plan_active",
            "day_plans",
            ["user_id", "plan_date", "status"],
            unique=True,
            postgresql_where=sa.text("status IN ('draft', 'confirmed', 'active')"),
            sqlite_where=sa.text("status IN ('draft', 'confirmed', 'active')"),
        )


def downgrade() -> None:
    if not _table_exists("day_plans"):
        return
    op.drop_index("uq_day_plan_active", table_name="day_plans")
    op.create_unique_constraint(
        "uq_day_plan_active",
        "day_plans",
        ["user_id", "plan_date", "status"],
    )
