# 术语与数据模型统一 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 4 张重叠的日程表（calendar_events / day_plans / plan_items / task_items）合并为 2 张表（scheduled_items / tasks），统一全栈术语为"安排"（有固定时间）和"任务"（无固定时间）。

**Architecture:** 后端新增 `scheduled_items` 表替代 calendar_events + day_plans + plan_items；重写 Service/Route/Tool 层引用新表；前端统一使用 `ScheduledItem` 类型，不再区分 event/plan_item。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / Next.js / Ant Design

---

## 文件结构变更

### 新建文件
```
backend/app/models/scheduled_item.py       # ScheduledItem ORM 模型
backend/app/schemas/scheduled_item.py       # 安排相关 Pydantic schema
backend/app/api/routes/scheduled_items.py   # /api/scheduled-items 路由
backend/app/services/scheduled_item_service.py  # 业务服务
backend/alembic/versions/0009_scheduled_items.py # 数据迁移
```

### 待删除文件
```
backend/app/api/routes/calendar_events.py
backend/app/api/routes/day_plans.py
backend/app/api/routes/plan_items.py
backend/app/schemas/plan.py
backend/app/services/calendar_event_service.py
backend/app/services/day_plan_service.py
backend/app/services/plan_item_service.py
```

### 待修改文件
```
backend/app/models/schedule.py              # 移除旧模型，保留 Conflict/Reminder
backend/app/models/enums.py                 # 新增 ScheduledItemStatus, 简化 TaskStatus
backend/app/models/__init__.py              # 更新导出
backend/app/schemas/schedule.py             # 移除 CalendarEvent schema
backend/app/schemas/conflict.py             # 更新引用
backend/app/schemas/reminder.py             # 更新引用
backend/app/services/conflict_service.py    # 引用 scheduled_items
backend/app/services/reminder_service.py    # 引用 scheduled_items
backend/app/services/daily_notification_service.py  # 引用 scheduled_items
backend/app/tools/registry.py               # 重命名/重写工具
backend/app/tools/schemas.py                # 更新工具入参 schema
backend/app/agent/state.py                  # 更新 AgentState 字段
backend/app/agent/graph.py                  # 更新意图名/处理器
backend/app/agent/parsing.py                # 更新 fallback 文案
backend/app/agent/schemas.py                # 更新 LLM 输出 schema
backend/app/main.py                         # 更新 title
backend/app/workers/reminder_worker.py      # 更新引用

web/lib/dashboard.ts                        # 更新 API 调用和类型
web/lib/types.ts                            # 更新类型定义
web/app/dashboard/today/page.tsx            # 统一时间轴展示
web/app/dashboard/calendar/page.tsx         # 统一为单套 API
web/app/dashboard/tasks/page.tsx            # 更新任务展示
web/app/dashboard/conflicts/page.tsx        # 更新文案
web/components/dashboard-shell.tsx          # 菜单"待办"→"任务"

backend/tests/*.py                          # 所有测试文件
```

---

### Task 1: 更新枚举定义

**Files:**
- Modify: `backend/app/models/enums.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 新增 ScheduledItemStatus 枚举，简化 TaskStatus**

`backend/app/models/enums.py` 中新增：

```python
class ScheduledItemStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class ScheduledItemSource(StrEnum):
    MANUAL = "manual"
    AGENT = "agent"
    PLAN = "plan"
```

同时精简 `TaskStatus`，移除已不用的 `planned`：

```python
class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"
```

将 `ReminderTargetType` 中的 `EVENT` / `PLAN` 改为 `SCHEDULED_ITEM`：

```python
class ReminderTargetType(StrEnum):
    SCHEDULED_ITEM = "scheduled_item"
    TASK = "task"
    OTHER = "other"
```

- [ ] **Step 2: 更新 `__init__.py` 导出**

`backend/app/models/__init__.py` 中增加 `ScheduledItem` 的 import：

```python
from app.models.scheduled_item import ScheduledItem
```

- [ ] **Step 3: 运行 ruff 检查**

Run: `cd backend && uv run ruff check app/models/enums.py app/models/__init__.py`
Expected: no errors

---

### Task 2: 创建 ScheduledItem ORM 模型

**Files:**
- Create: `backend/app/models/scheduled_item.py`

- [ ] **Step 1: 创建模型文件**

`backend/app/models/scheduled_item.py`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ScheduledItemSource, ScheduledItemStatus


class ScheduledItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_items"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemSource.MANUAL.value
    )
    source_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    remind_before_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemStatus.ACTIVE.value
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: 创建模型后检查**

Run: `cd backend && uv run ruff check app/models/scheduled_item.py`
Expected: no errors

---

### Task 3: 创建 Alembic 迁移脚本

**Files:**
- Create: `backend/alembic/versions/0009_scheduled_items.py`
- Modify: `backend/app/models/schedule.py`（准备删除旧表，但先注释掉关联）

- [ ] **Step 1: 生成迁移脚本**

Run: `cd backend && uv run alembic revision --autogenerate -m "scheduled_items_unification"`

如果 autogenerate 生成的脚本不完整，手动补写以下内容：

```python
"""scheduled_items_unification

Revision ID: 0009
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. 创建 scheduled_items 表
    op.create_table(
        "scheduled_items",
        sa.Column("id", UUID(), nullable=False),
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_items_user_time", "scheduled_items", ["user_id", "start_time"])
    op.create_index("ix_scheduled_items_user_status", "scheduled_items", ["user_id", "status"])
    op.create_index("ix_scheduled_items_source_task", "scheduled_items", ["source_task_id"])
    op.create_index("ix_scheduled_items_date", "scheduled_items", [sa.text("(start_time::date)")])

    # 2. 从 calendar_events 迁移数据
    conn = op.get_bind()
    calendar_events = conn.execute(
        sa.text("SELECT * FROM calendar_events WHERE status != 'deleted'")
    ).mappings()

    for row in calendar_events:
        conn.execute(
            sa.text("""
                INSERT INTO scheduled_items
                    (id, user_id, title, description, start_time, end_time,
                     timezone, location, source, source_task_id,
                     remind_before_minutes, status, sort_order, created_at, updated_at)
                VALUES
                    (:id, :user_id, :title, :description, :start_time, COALESCE(:end_time, :start_time + INTERVAL '1 hour'),
                     :timezone, :location, :source, NULL,
                     :remind_before_minutes, :status, 0, :created_at, :updated_at)
            """),
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "description": row["description"],
                "start_time": row["start_time"],
                "end_time": row["end_time"] or row["start_time"],
                "timezone": row["timezone"],
                "location": row["location"],
                "source": "agent" if row["source"] == "agent" else "manual",
                "remind_before_minutes": row.get("remind_before_minutes"),
                "status": "active" if row["status"] == "active" else row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    # 3. 从 plan_items 迁移数据（需关联 day_plans.status）
    plan_items = conn.execute(
        sa.text("""
            SELECT pi.*, dp.status AS plan_status
            FROM plan_items pi
            JOIN day_plans dp ON dp.id = pi.day_plan_id
            WHERE pi.status != 'deleted'
        """)
    ).mappings()

    for row in plan_items:
        # 判断目标状态
        if row["plan_status"] == "draft" and row["status"] == "planned":
            target_status = "draft"
        elif row["plan_status"] in ("confirmed", "active") and row["status"] == "planned":
            target_status = "active"
        elif row["status"] in ("in_progress", "completed"):
            target_status = row["status"]
        elif row["status"] in ("cancelled", "skipped"):
            target_status = "cancelled"
        else:
            target_status = "active"

        conn.execute(
            sa.text("""
                INSERT INTO scheduled_items
                    (id, user_id, title, description, start_time, end_time,
                     timezone, location, source, source_task_id,
                     remind_before_minutes, status, sort_order, created_at, updated_at)
                VALUES
                    (:id, :user_id, :title, NULL, :start_time, :end_time,
                     'Asia/Shanghai', NULL, 'plan', :source_task_id,
                     NULL, :status, :sort_order, :created_at, :updated_at)
            """),
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "source_task_id": row["ref_id"] if row["item_type"] == "task" else None,
                "status": target_status,
                "sort_order": row["sort_order"] or 0,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )

    # 4. 迁移 reminder_jobs 引用
    conn.execute(
        sa.text("UPDATE reminder_jobs SET target_type = 'scheduled_item' WHERE target_type IN ('event', 'plan')")
    )

    # 5. 迁移 schedule_conflicts 引用（related_item_ids 中的 calendar_events/plan_items id 映射为 scheduled_items id，字段名不改动）
    # scheduled_items 表的 id 与 calendar_events、plan_items 的 id 保持一致（用原 UUID）

    # 6. 删除旧表
    op.drop_table("plan_items")
    op.drop_table("day_plans")
    op.drop_table("calendar_events")


def downgrade() -> None:
    # 不支持回退
    pass
```

- [ ] **Step 2: 执行迁移**

Run: `cd backend && uv run alembic upgrade head`
Expected: tables created, data migrated

---

### Task 4: 更新存量模型（schedule.py）移除旧表模型

**Files:**
- Modify: `backend/app/models/schedule.py`

- [ ] **Step 1: 删除 CalendarEvent、TaskItem、DayPlan、PlanItem 类**

保留 `ScheduleConflict` 和 `ReminderJob`。删除后的文件内容：

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ConflictSeverity,
    ConflictStatus,
    ConflictType,
    ReminderStatus,
    ReminderTargetType,
)

json_type = JSON().with_variant(JSONB, "postgresql")


class ScheduleConflict(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedule_conflicts"
    __table_args__ = (
        Index("ix_conflicts_user_status", "user_id", "status"),
        Index("ix_conflicts_user_type", "user_id", "conflict_type"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conflict_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ConflictType.TIME_OVERLAP.value
    )
    severity: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConflictSeverity.MEDIUM.value
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    related_item_ids: Mapped[dict[str, Any] | None] = mapped_column(json_type, default=dict)
    suggestion: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ConflictStatus.OPEN.value
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReminderJob(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reminder_jobs"
    __table_args__ = (
        Index("ix_reminders_user_status", "user_id", "status"),
        Index("ix_reminders_trigger_time", "trigger_time"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ReminderTargetType.SCHEDULED_ITEM.value
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ReminderStatus.PENDING.value
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 2: 更新 models/__init__.py 移除旧模型的导出引用**

确保 `__init__.py` 不再导出 `CalendarEvent`、`TaskItem`、`DayPlan`、`PlanItem`。

---

### Task 5: 创建 ScheduledItemService

**Files:**
- Create: `backend/app/services/scheduled_item_service.py`

- [ ] **Step 1: 创建服务类**

```python
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ScheduledItemStatus
from app.models.scheduled_item import ScheduledItem
from app.services.reminder_service import ReminderService


class ScheduledItemService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str = "Asia/Shanghai",
        description: str | None = None,
        location: str | None = None,
        source: str = "manual",
        source_task_id: str | None = None,
        remind_before_minutes: int | None = None,
        status: str = "active",
    ) -> ScheduledItem:
        item = ScheduledItem(
            user_id=user_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            description=description,
            location=location,
            source=source,
            source_task_id=source_task_id,
            remind_before_minutes=remind_before_minutes,
            status=status,
        )
        self.db.add(item)
        self.db.flush()

        if remind_before_minutes and remind_before_minutes > 0 and status != "draft":
            reminder = ReminderService(self.db)
            reminder.create_from_scheduled_item(
                user_id=user_id,
                scheduled_item_id=item.id,
                title=title,
                trigger_time=start_time,
                remind_before_minutes=remind_before_minutes,
            )

        return item

    def get(self, user_id: str, item_id: str) -> ScheduledItem | None:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.id == item_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        )
        return self.db.scalar(stmt)

    def list_by_date_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        status: str | None = None,
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start_time,
            ScheduledItem.start_time <= end_time,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if status:
            conditions.append(ScheduledItem.status == status)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def list_by_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        start = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=None)
        end = start.replace(hour=23, minute=59, second=59)
        return self.list_by_date_range(user_id, start, end)

    def list_by_task_id(self, user_id: str, task_id: str) -> list[ScheduledItem]:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        )
        return list(self.db.scalars(stmt))

    def update(
        self,
        item: ScheduledItem,
        title: str | None = None,
        description: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        timezone: str | None = None,
        location: str | None = None,
        remind_before_minutes: int | None = None,
        status: str | None = None,
    ) -> ScheduledItem:
        if title is not None:
            item.title = title
        if description is not None:
            item.description = description
        if start_time is not None:
            item.start_time = start_time
        if end_time is not None:
            item.end_time = end_time
        if timezone is not None:
            item.timezone = timezone
        if location is not None:
            item.location = location
        if remind_before_minutes is not None:
            item.remind_before_minutes = remind_before_minutes
        if status is not None:
            item.status = status
        self.db.flush()
        return item

    def mark_completed(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.COMPLETED.value
        self.db.flush()
        return item

    def soft_delete(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.DELETED.value
        self.db.flush()
        return item

    def search(
        self, user_id: str, keyword: str, on_date: date | None = None
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.title.ilike(f"%{keyword}%"),
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if on_date:
            start = datetime(on_date.year, on_date.month, on_date.day)
            end = start.replace(hour=23, minute=59, second=59)
            conditions.append(ScheduledItem.start_time >= start)
            conditions.append(ScheduledItem.start_time <= end)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> int:
        """确认某日所有 draft 状态的安排"""
        start = datetime(plan_date.year, plan_date.month, plan_date.day)
        end = start.replace(hour=23, minute=59, second=59)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start,
            ScheduledItem.start_time <= end,
            ScheduledItem.status == ScheduledItemStatus.DRAFT.value,
        )
        items = list(self.db.scalars(stmt))
        for item in items:
            item.status = ScheduledItemStatus.ACTIVE.value
        self.db.flush()
        return len(items)

    def generate_day_drafts(
        self, user_id: str, plan_date: date, task_service: object
    ) -> list[ScheduledItem]:
        """为某日生成安排草案：将未完成且未排入当天的任务填入空闲时段"""

        from app.models.enums import TaskStatus

        # 1. 获取当天已有的安排
        existing = self.list_by_date(user_id, plan_date)

        # 2. 获取当天已排入的任务 ID
        planned_task_ids = {
            si.source_task_id for si in existing if si.source_task_id
        }

        # 3. 获取待排入的任务（pending，未排入当天）
        pending_tasks = [
            t for t in task_service.list_pending_tasks(user_id)
            if t.id not in planned_task_ids
        ]

        if not pending_tasks or not task_service:
            return []

        # 4. 简单的贪心填充：从 09:00 开始，按任务耗时填充到空闲时段
        from datetime import timedelta

        base = datetime(plan_date.year, plan_date.month, plan_date.day, 9, 0)
        created: list[ScheduledItem] = []
        for task in pending_tasks:
            mins = task.estimated_minutes or 60
            slot_start = base
            slot_end = slot_start + timedelta(minutes=mins)

            # 检查是否与已有安排冲突
            conflict = False
            for ex in existing:
                if ex.start_time < slot_end and ex.end_time > slot_start:
                    conflict = True
                    base = ex.end_time
                    break

            if conflict:
                continue

            item = self.create(
                user_id=user_id,
                title=task.title,
                start_time=slot_start,
                end_time=slot_end,
                source="plan",
                source_task_id=task.id,
                status="draft",
            )
            created.append(item)
            base = slot_end

        return created
```

- [ ] **Step 2: 检查语法**

Run: `cd backend && uv run ruff check app/services/scheduled_item_service.py`
Expected: no errors

---

### Task 6: 创建 ScheduledItem Schemas

**Files:**
- Create: `backend/app/schemas/scheduled_item.py`

- [ ] **Step 1: 创建 schema 文件**

```python
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ScheduledItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_time: datetime
    end_time: datetime
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    location: str | None = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=32)
    source_task_id: str | None = None
    remind_before_minutes: int | None = Field(default=None, ge=0, le=24 * 60)


class ScheduledItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    status: str | None = Field(default=None, max_length=32)


class ScheduledItemDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    timezone: str
    location: str | None = None
    source: str
    source_task_id: str | None = None
    remind_before_minutes: int | None = None
    status: str
    sort_order: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScheduledItemListResponse(BaseModel):
    items: list[ScheduledItemDTO]


class GenerateDayDraftsRequest(BaseModel):
    include_pending_tasks: bool = True
    auto_detect_conflicts: bool = True


class ConfirmDayDraftsRequest(BaseModel):
    plan_date: date
```

---

### Task 7: 创建 scheduled_items API 路由

**Files:**
- Create: `backend/app/api/routes/scheduled_items.py`

- [ ] **Step 1: 创建路由文件**

```python
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.scheduled_item import (
    ConfirmDayDraftsRequest,
    GenerateDayDraftsRequest,
    ScheduledItemCreateRequest,
    ScheduledItemDTO,
    ScheduledItemListResponse,
    ScheduledItemUpdateRequest,
)
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService

router = APIRouter(prefix="/api/scheduled-items", tags=["scheduled_items"])


def _to_dto(item: object) -> ScheduledItemDTO:
    i = item
    return ScheduledItemDTO(
        id=i.id,
        title=i.title,
        description=i.description,
        start_time=i.start_time,
        end_time=i.end_time,
        timezone=i.timezone,
        location=i.location,
        source=i.source,
        source_task_id=i.source_task_id,
        remind_before_minutes=i.remind_before_minutes,
        status=i.status,
        sort_order=i.sort_order,
        created_at=i.created_at,
        updated_at=i.updated_at,
    )


@router.post("", response_model=ApiResponse[ScheduledItemDTO])
def create_scheduled_item(
    payload: ScheduledItemCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.create(
        user_id=current_user.id,
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone=payload.timezone,
        description=payload.description,
        location=payload.location,
        source=payload.source,
        source_task_id=payload.source_task_id,
        remind_before_minutes=payload.remind_before_minutes,
    )
    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已创建")


@router.get("", response_model=ApiResponse[ScheduledItemListResponse])
def list_scheduled_items(
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    date: date | None = Query(None),
    keyword: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemListResponse]:
    service = ScheduledItemService(db)

    if keyword:
        items = service.search(current_user.id, keyword, date)
    elif date:
        items = service.list_by_date(current_user.id, date)
    elif start_time and end_time:
        items = service.list_by_date_range(current_user.id, start_time, end_time, status)
    else:
        items = []

    return ApiResponse(
        data=ScheduledItemListResponse(items=[_to_dto(item) for item in items]),
        message="安排查询完成",
    )


@router.get("/{item_id}", response_model=ApiResponse[ScheduledItemDTO])
def get_scheduled_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    return ApiResponse(data=_to_dto(item))


@router.patch("/{item_id}", response_model=ApiResponse[ScheduledItemDTO])
def update_scheduled_item(
    item_id: str,
    payload: ScheduledItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    item = service.update(
        item,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone=payload.timezone,
        location=payload.location,
        remind_before_minutes=payload.remind_before_minutes,
        status=payload.status,
    )
    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已更新")


@router.delete("/{item_id}", response_model=ApiResponse)
def delete_scheduled_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    service.soft_delete(item)
    db.commit()
    return ApiResponse(message="安排已删除")


@router.patch("/{item_id}/complete", response_model=ApiResponse[ScheduledItemDTO])
def complete_scheduled_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    item = service.mark_completed(item)
    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已完成")


@router.post("/generate/{plan_date}", response_model=ApiResponse[ScheduledItemListResponse])
def generate_day_drafts_by_date(
    plan_date: date,
    payload: GenerateDayDraftsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemListResponse]:
    service = ScheduledItemService(db)
    task_service = TaskService(db)
    items = service.generate_day_drafts(
        user_id=current_user.id,
        plan_date=plan_date,
        task_service=task_service,
    )
    db.commit()
    return ApiResponse(
        data=ScheduledItemListResponse(items=[_to_dto(item) for item in items]),
        message="安排草案已生成",
    )


@router.post("/confirm", response_model=ApiResponse)
def confirm_day_drafts(
    payload: ConfirmDayDraftsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    service = ScheduledItemService(db)
    count = service.confirm_drafts_for_date(current_user.id, payload.plan_date)
    db.commit()
    return ApiResponse(message=f"已确认 {count} 项安排")
```

- [ ] **Step 2: 注册路由**

在 `backend/app/main.py` 中找到 router include 的位置，添加：

```python
from app.api.routes.scheduled_items import router as scheduled_items_router
app.include_router(scheduled_items_router)
```

同时移除旧的 calendar_events、day_plans、plan_items router import。

---

### Task 8: 更新 TaskService

**Files:**
- Modify: `backend/app/services/task_service.py`

- [ ] **Step 1: 新增 `list_pending_tasks` 方法**

```python
def list_pending_tasks(self, user_id: str) -> list[TaskItem]:
    stmt = select(TaskItem).where(
        TaskItem.user_id == user_id,
        TaskItem.status == "pending",
    ).order_by(TaskItem.priority.desc(), TaskItem.deadline.asc())
    return list(self.db.scalars(stmt))
```

同时确保 `TaskItem` 的 import 改为从当前 model 导入（迁移后表名仍是 `task_items`，ORM 名改为 `Task` 待后续决定，当前使用中间状态保留旧名但不影响使用）。

---

### Task 9: 更新 ConflictService

**Files:**
- Modify: `backend/app/services/conflict_service.py`

- [ ] **Step 1: 将所有 CalendarEvent 引用改为 ScheduledItem**

```python
# 替换 import
from app.models.scheduled_item import ScheduledItem

# detect_all_conflicts 方法：
# 原 CalendarEvent → ScheduledItem
# 原 event → item
# 原 start_time/end_time 字段不变（ScheduledItem 也有这些字段）
# 冲突 title 改为 "安排冲突："
```

具体改动：
- `CalendarEvent` → `ScheduledItem`
- `"日程冲突："` → `"安排冲突："`
- `"请调整其中一个日程时间"` → `"请调整其中一个安排时间"`
- `calendar_events` 表的引用全部替换为 `scheduled_items`

---

### Task 10: 更新 ReminderService

**Files:**
- Modify: `backend/app/services/reminder_service.py`

- [ ] **Step 1: 新增 `create_from_scheduled_item` 方法**

```python
def create_from_scheduled_item(
    self,
    user_id: str,
    scheduled_item_id: str,
    title: str,
    trigger_time: datetime,
    remind_before_minutes: int,
    conversation_id: str | None = None,
) -> ReminderJob:
    reminder = ReminderJob(
        user_id=user_id,
        target_type=ReminderTargetType.SCHEDULED_ITEM.value,
        target_id=scheduled_item_id,
        title=title,
        trigger_time=trigger_time,
        conversation_id=conversation_id or user_id,
    )
    self.db.add(reminder)
    self.db.flush()
    return reminder
```

同时更新现有方法中对 `target_type = 'event'` 的判断，改为 `'scheduled_item'`。

---

### Task 11: 更新 Tool Schemas

**Files:**
- Modify: `backend/app/tools/schemas.py`

- [ ] **Step 1: 重命名 event 相关 schema 为 scheduled_item**

```python
# 新增
class CreateScheduledItemArgs(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    location: str | None = Field(default=None, max_length=255)
    remind_before_minutes: int | None = Field(default=0, ge=0)


class QueryScheduledItemsArgs(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = "Asia/Shanghai"


class UpdateScheduledItemArgs(BaseModel):
    item_id: str
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    timezone: str | None = None
    location: str | None = None
    remind_before_minutes: int | None = None


class DeleteScheduledItemArgs(BaseModel):
    item_id: str
```

- [ ] **Step 2: 保留老的 schema 名作为别名（兼容），或直接删除**

建议直接删除旧的 `CreateEventArgs`、`QueryEventsArgs`、`UpdateEventArgs`、`DeleteEventArgs`、`SearchEventCandidatesArgs`。

更新 `ConfirmPlanArgs`：
```python
class ConfirmPlanArgs(BaseModel):
    plan_date: date  # 改为按日期确认，而非 plan_id
```

---

### Task 12: 更新 ToolRegistry

**Files:**
- Modify: `backend/app/tools/registry.py`

- [ ] **Step 1: 重写工具注册函数**

将 `create_event` 改为 `create_scheduled_item`，逻辑改为操作 `ScheduledItemService`：

```python
def create_scheduled_item(
    args: dict[str, Any], user_id: str, conversation_id: str, session: Session
) -> ToolResult:
    payload = CreateScheduledItemArgs.model_validate(args)
    service = ScheduledItemService(session)
    item = service.create(
        user_id=user_id,
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time or payload.start_time,
        timezone=payload.timezone,
        location=payload.location,
        remind_before_minutes=payload.remind_before_minutes,
        source="agent",
    )
    session.commit()
    return ToolResult(data=_item_to_dict(item), message="安排已创建")
```

同样更新 `query_scheduled_items`、`update_scheduled_item`、`delete_scheduled_item`。

`confirm_plan` 改为按日期确认：
```python
def confirm_plan(
    args: dict[str, Any], user_id: str, conversation_id: str, session: Session
) -> ToolResult:
    payload = ConfirmPlanArgs.model_validate(args)
    service = ScheduledItemService(session)
    count = service.confirm_drafts_for_date(user_id, payload.plan_date)
    session.commit()
    return ToolResult(data={"confirmed_count": count}, message="安排已确认")
```

`plan_tasks_into_day` 改为使用 `ScheduledItemService.generate_day_drafts`。

---

### Task 13: 更新 AgentState

**Files:**
- Modify: `backend/app/agent/state.py`

- [ ] **Step 1: 更新字段名**

```python
class AgentState(BaseModel):
    user_id: str
    conversation_id: str
    channel: str = "wechat"
    input_text: str
    current_time: datetime
    timezone: str = "Asia/Shanghai"

    user_settings: dict[str, Any] | None = None
    pending_state: dict[str, Any] | None = None
    intent: str | None = None
    extracted: dict[str, Any] | None = None
    candidate_scheduled_items: list[dict[str, Any]] = Field(default_factory=list)
    scheduled_items: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    free_slots: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    graph_trace: list[str] = Field(default_factory=list)
    final_response: str | None = None
    success: bool = False
    error: str | None = None
```

关键变化：
- `candidate_events` → `candidate_scheduled_items`
- `events` → `scheduled_items`
- 删除 `draft_plan`

---

### Task 14: 更新 Agent Graph

**Files:**
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/parsing.py`

- [ ] **Step 1: 更新 `parsing.py` 的 fallback 文案**

```python
# infer_event_title fallback
return extract_keyword_after_time(text) or "安排"
```

- [ ] **Step 2: 更新 graph.py 中的意图名称**

所有 `create_event` → `create_scheduled_item`，`query_events` → `query_scheduled_items`，
`update_event` → `update_scheduled_item`，`delete_event` → `delete_scheduled_item`。

Agent prompt 中的"你是一个日程规划 Agent"→"你是一个安排规划 Agent"。

`_candidate_line` 中的"日程"→"安排"。

- [ ] **Step 3: 更新 `main.py` title**

```python
app = FastAPI(title="微信智能安排规划 Agent", version="0.1.0", lifespan=lifespan)
```

---

### Task 15: 更新 ReminderWorker

**Files:**
- Modify: `backend/app/workers/reminder_worker.py`

- [ ] **Step 1: 更新 reminder 发送逻辑中的 target_type 判断**

```python
# 旧
if reminder.target_type == "event":
    event = calendar_event_service.get(...)
# 新
if reminder.target_type == "scheduled_item":
    item = scheduled_item_service.get(...)
```

---

### Task 16: 更新 DailyNotificationService

**Files:**
- Modify: `backend/app/services/daily_notification_service.py`

- [ ] **Step 1: 将 CalendarEvent 引用改为 ScheduledItem**

```python
from app.models.scheduled_item import ScheduledItem
# 查询改为 ScheduledItem
```

---

### Task 17: 更新前端类型定义

**Files:**
- Modify: `web/lib/dashboard.ts`
- Modify: `web/lib/types.ts`

- [ ] **Step 1: 定义 ScheduledItem 类型**

`web/lib/types.ts` 中新增：

```typescript
export interface ScheduledItem {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  timezone: string;
  location: string | null;
  source: string;
  source_task_id: string | null;
  remind_before_minutes: number | null;
  status: string;
  sort_order: number | null;
}
```

移除 `CalendarEventItem`、`DayPlan`、`DayPlanItem` 等旧类型。

- [ ] **Step 2: 更新 `dashboard.ts` 中的 API 函数**

```typescript
// 统一 API 调用
export async function loadScheduledItems(
  params: { start_time?: string; end_time?: string; date?: string; keyword?: string }
): Promise<ScheduledItem[]> {
  const query = new URLSearchParams();
  if (params.start_time) query.set("start_time", params.start_time);
  if (params.end_time) query.set("end_time", params.end_time);
  if (params.date) query.set("date", params.date);
  if (params.keyword) query.set("keyword", params.keyword);
  const resp = await requestJson<ApiResponse<{ items: ScheduledItem[] }>>(
    `/api/scheduled-items?${query.toString()}`
  );
  return resp.data.items;
}

export async function createScheduledItem(
  data: Partial<ScheduledItem> & { title: string; start_time: string; end_time: string }
): Promise<ScheduledItem> {
  const resp = await requestJson<ApiResponse<ScheduledItem>>("/api/scheduled-items", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return resp.data;
}

export async function updateScheduledItem(
  id: string,
  data: Partial<ScheduledItem>
): Promise<ScheduledItem> {
  const resp = await requestJson<ApiResponse<ScheduledItem>>(`/api/scheduled-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return resp.data;
}

export async function deleteScheduledItem(id: string): Promise<void> {
  await requestJson(`/api/scheduled-items/${id}`, { method: "DELETE" });
}

export async function completeScheduledItem(id: string): Promise<ScheduledItem> {
  const resp = await requestJson<ApiResponse<ScheduledItem>>(
    `/api/scheduled-items/${id}/complete`, { method: "PATCH" }
  );
  return resp.data;
}

export async function generateDayDrafts(
  planDate: string,
  options?: { include_pending_tasks?: boolean; auto_detect_conflicts?: boolean }
): Promise<ScheduledItem[]> {
  const resp = await requestJson<ApiResponse<{ items: ScheduledItem[] }>>(
    `/api/scheduled-items/generate/${planDate}`,
    { method: "POST", body: JSON.stringify(options || {}) }
  );
  return resp.data.items;
}

export async function confirmDayDrafts(planDate: string): Promise<void> {
  await requestJson("/api/scheduled-items/confirm", {
    method: "POST",
    body: JSON.stringify({ plan_date: planDate }),
  });
}
```

删除旧的 `loadCalendarEvents`、`createCalendarEvent`、`loadDayPlan`、`generateDayPlan`、`confirmDayPlan`、`createPlanItem`、`updatePlanItem`、`completePlanItem`、`deletePlanItem` 等函数。

---

### Task 18: 更新前端今日页

**Files:**
- Modify: `web/app/dashboard/today/page.tsx`

- [ ] **Step 1: 替换类型引用和数据加载**

```typescript
// 删除
import { ..., CalendarEventItem, DayPlan, DayPlanItem, ... } from "@/lib/dashboard";
// 新增
import { ..., ScheduledItem, ... } from "@/lib/dashboard";

// 将所有 kind: "event" | "plan_item" 的逻辑移除，统一使用 ScheduledItem
// 时间轴数据加载改为从 loadScheduledItems 获取
```

关键改动：
- 所有 `${item.kind === "plan_item" ? "安排项" : "安排"}` → `"安排"`
- 所有 `${entry.kind === "plan_item" ? 90 : 60}` → `60`（统一默认值）
- 去除青色/蓝色区分标签

- [ ] **Step 2: 移除"计划完成度"文案，改为"今日完成度"**

---

### Task 19: 更新前端日历页

**Files:**
- Modify: `web/app/dashboard/calendar/page.tsx`

- [ ] **Step 1: 移除 DayPlan 相关逻辑**

删除 `loadDayPlan`、`generateDayPlan`、`confirmDayPlan`、`createPlanItem`、`updatePlanItem`、`completePlanItem`、`deletePlanItem` 的调用。

日历页所有日程数据从 `loadScheduledItems` 加载。

移除 `DayTimelineEntry` 类型的 `kind: "event" | "plan_item"` 联合类型，统一使用 `ScheduledItem`。

移除 `PlanItemFormValues` 类型和对应弹窗。

- [ ] **Step 2: 统一 CRUD 操作**

日历上的每一项都用 `createScheduledItem` / `updateScheduledItem` / `deleteScheduledItem` / `completeScheduledItem`，不再区分两类。

---

### Task 20: 更新前端任务页和冲突页

**Files:**
- Modify: `web/app/dashboard/tasks/page.tsx`
- Modify: `web/app/dashboard/conflicts/page.tsx`
- Modify: `web/components/dashboard-shell.tsx`

- [ ] **Step 1: 任务页更新**

`tasks/page.tsx`：确认 API 调用使用的是 `/api/tasks`，无需大改。检查是否有"计划"相关文案，改为"安排"。

- [ ] **Step 2: 冲突页更新**

`conflicts/page.tsx`：将"日程冲突"文案改为"安排冲突"。

- [ ] **Step 3: 菜单更新**

`dashboard-shell.tsx`：`"待办"` → `"任务"`

---

### Task 21: 删除废弃的后端代码

**Files:**
- Delete: `backend/app/api/routes/calendar_events.py`
- Delete: `backend/app/api/routes/day_plans.py`
- Delete: `backend/app/api/routes/plan_items.py`
- Delete: `backend/app/schemas/plan.py`
- Delete: `backend/app/services/calendar_event_service.py`
- Delete: `backend/app/services/day_plan_service.py`
- Delete: `backend/app/services/plan_item_service.py`

- [ ] **Step 1: 从 main.py 中移除废弃的 router include**

- [ ] **Step 2: 从 models/__init__.py 中移除旧模型引用**

- [ ] **Step 3: 删除对应的测试文件引用**

---

### Task 22: 更新测试文件

**Files:**
- Modify: `backend/tests/test_health_and_auth.py`
- Modify: `backend/tests/test_calendar_events_route.py`
- Modify: `backend/tests/test_conflicts_route.py`
- Modify: `backend/tests/test_agent_debug_flow.py`
- Modify: `backend/tests/test_agent_debug_route.py`
- Modify: `backend/tests/test_web_agent_message_route.py`
- Modify: `backend/tests/test_wechat_channel_adapter.py`
- Modify: `backend/tests/test_wechat_inbound.py`
- Modify: `backend/tests/test_daily_notification.py`
- Modify: `backend/tests/test_reminder_worker.py`
- Delete: `backend/tests/test_plan_items_route.py`
- Delete: `backend/tests/test_calendar_events_route.py`（重写为 test_scheduled_items_route.py）

- [ ] **Step 1: 更新所有测试中的断言文案**

所有 `"已为你创建日程"` → `"已为你创建安排"`
所有 `"日程不存在"` → `"安排不存在"`

- [ ] **Step 2: 创建新的 scheduled_items 测试**

创建 `backend/tests/test_scheduled_items_route.py` 覆盖基本 CRUD。

- [ ] **Step 3: 运行全部测试**

Run: `cd backend && uv run pytest -x -v`
Expected: all tests pass

---

### 自检清单

1. **Spec 覆盖**：每一条 spec 中的变更点都能在这个计划中找到对应的 Task
2. **占位符检查**：所有步骤都有实际代码，没有"待补充"、"TODO"
3. **类型一致性**：`ScheduledItem` 类型在前端和后端的字段名、类型一致
4. **执行顺序**：数据模型 → 迁移 → Service → API → Tools → Agent → 前端 → 清理 → 测试
