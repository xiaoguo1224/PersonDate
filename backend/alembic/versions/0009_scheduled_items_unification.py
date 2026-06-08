"""scheduled_items unification: merge calendar_events + day_plans + plan_items

Revision ID: 0009_scheduled_items_unification
Revises: 0008_add_wechat_channel_inbound_messages
Create Date: 2026-06-06
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision: str = "0009_scheduled_items_unification"
down_revision: str | None = "0008_add_wechat_channel_inbound_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    bind = op.get_bind()

    # 1. 创建 scheduled_items 表
    if not _table_exists("scheduled_items"):
        op.create_table(
            "scheduled_items",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai"),
            sa.Column("location", sa.String(255), nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
            sa.Column("source_task_id", sa.String(36), sa.ForeignKey("task_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("remind_before_minutes", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("sort_order", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("ix_scheduled_items_user_time", "scheduled_items"):
        op.create_index("ix_scheduled_items_user_time", "scheduled_items", ["user_id", "start_time"])
    if not _index_exists("ix_scheduled_items_user_status", "scheduled_items"):
        op.create_index("ix_scheduled_items_user_status", "scheduled_items", ["user_id", "status"])
    if not _index_exists("ix_scheduled_items_source_task", "scheduled_items"):
        op.create_index("ix_scheduled_items_source_task", "scheduled_items", ["source_task_id"])

    # 2. 从 calendar_events 迁移数据（使用 SQLAlchemy 核心查询）
    scheduled = sa.Table("scheduled_items", sa.MetaData(), autoload_with=bind)
    existing_ids = set(bind.execute(sa.select(scheduled.c.id)).scalars().all())

    if _table_exists("calendar_events"):
        calendar_events = sa.Table("calendar_events", sa.MetaData(), autoload_with=bind)
        rows = bind.execute(
            sa.select(calendar_events).where(calendar_events.c.status != "deleted")
        ).mappings()

        for row in rows:
            if row["id"] in existing_ids:
                continue
            end = row["end_time"] or (row["start_time"] + timedelta(hours=1))
            bind.execute(
                scheduled.insert().values(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    description=row["description"],
                    start_time=row["start_time"],
                    end_time=end,
                    timezone=row["timezone"] or "Asia/Shanghai",
                    location=row["location"],
                    source="agent" if row["source"] == "agent" else "manual",
                    remind_before_minutes=row["remind_before_minutes"],
                    status="active" if row["status"] == "active" else row["status"],
                    sort_order=0,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
            existing_ids.add(row["id"])

    # 3. 从 plan_items 迁移数据
    if _table_exists("plan_items") and _table_exists("day_plans"):
        plan_items = sa.Table("plan_items", sa.MetaData(), autoload_with=bind)
        day_plans_t = sa.Table("day_plans", sa.MetaData(), autoload_with=bind)

        day_plan_map: dict[str, str] = {}
        for dp in bind.execute(sa.select(day_plans_t)).mappings():
            day_plan_map[dp["id"]] = dp["status"]

        pi_rows = bind.execute(sa.select(plan_items)).mappings()
        for pi in pi_rows:
            if pi["id"] in existing_ids:
                continue
            plan_status = day_plan_map.get(pi["day_plan_id"], "draft")

            if plan_status == "draft" and pi["status"] == "planned":
                target_status = "draft"
            elif plan_status in ("confirmed", "active") and pi["status"] == "planned":
                target_status = "active"
            elif pi["status"] == "in_progress":
                target_status = "in_progress"
            elif pi["status"] == "completed":
                target_status = "completed"
            elif pi["status"] in ("cancelled", "skipped"):
                target_status = "cancelled"
            else:
                target_status = "active"

            source_task_id = pi["ref_id"] if pi["item_type"] == "task" else None

            bind.execute(
                scheduled.insert().values(
                    id=pi["id"],
                    user_id=pi["user_id"],
                    title=pi["title"],
                    start_time=pi["start_time"],
                    end_time=pi["end_time"],
                    timezone="Asia/Shanghai",
                    source="plan",
                    source_task_id=source_task_id,
                    status=target_status,
                    sort_order=pi["sort_order"] or 0,
                    created_at=pi["created_at"],
                    updated_at=pi["updated_at"],
                )
            )
            existing_ids.add(pi["id"])

    # 4. 迁移 reminder_jobs 引用
    if _table_exists("reminder_jobs"):
        reminder_jobs = sa.Table("reminder_jobs", sa.MetaData(), autoload_with=bind)
        bind.execute(
            reminder_jobs.update()
            .where(reminder_jobs.c.target_type.in_(["event", "plan"]))
            .values(target_type="scheduled_item")
        )

    # 5. 删除旧表
    if _table_exists("plan_items"):
        op.drop_table("plan_items")
    if _table_exists("day_plans"):
        op.drop_table("day_plans")
    if _table_exists("calendar_events"):
        op.drop_table("calendar_events")


def downgrade() -> None:
    pass
