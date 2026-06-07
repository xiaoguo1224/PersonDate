---
name: task-enhancement-design
description: 任务增强 — 日期范围、固定/弹性时间、自动排程与冲突重排、同步修改
---

# 任务增强设计文档

## 1. 概述

为 TaskItem 增加任务日期范围和灵活时间设置能力，使一个任务能在多天内自动展开为 ScheduledItem 实例，并在冲突时自动重排。

**现有状态**：TaskItem 是简单任务模型（标题、描述、时长、截止日期、优先级），ScheduledItem 通过 `source_task_id` 关联任务。目前每次只能为任务创建单个排期，重复性任务需手动逐天创建。

**目标**：

- 任务支持日期范围（每天/工作日/持续N天/自定义区间）
- 任务支持固定时间（每天同一时段）和弹性时间（只设时长，自动排空闲时段）
- 修改任务标题/时长/时间段时，同步更新所有关联的 ScheduledItem
- 自动排程时如与已有安排冲突，自动重排到下一个无冲突空闲时段
- 前端任务页面增加创建/编辑表单

## 2. 数据模型变更

### 2.1 TaskItem 新增字段

在 `backend/app/models/schedule.py` 的 TaskItem 模型中增加以下字段：

```python
# 日期范围类型
schedule_type: Mapped[str | None] = mapped_column(
    String(32), nullable=True, default=None
)
# schedule_type 枚举值：
#   "daily"          — 每天（到截止日期或无限期）
#   "weekdays"       — 仅工作日（周一到周五）
#   "duration_days"  — 持续N天（从 start_date 开始持续N天）
#   "custom_range"   — 自定义区间（start_date 到 end_date）

# 日期范围
start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

# 时间设置
time_type: Mapped[str | None] = mapped_column(
    String(32), nullable=True, default=None
)
# time_type 枚举值：
#   "fixed"     — 固定时间（每天同一时段，配合 scheduled_time / scheduled_end_time）
#   "flexible"  — 弹性时间（只设时长，自动排到空闲时段）

# 固定时间（time_type=fixed 时使用）
scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
scheduled_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

# 完成跟踪（用于 tracking completed days in recurring tasks）
completed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

**注意**：所有新增字段均为 `nullable=True` 且有默认值，不影响现有数据。

### 2.2 新增枚举

在 `backend/app/models/enums.py` 中新增：

```python
class TaskScheduleType(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    DURATION_DAYS = "duration_days"
    CUSTOM_RANGE = "custom_range"


class TaskTimeType(StrEnum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"
```

### 2.3 源类型扩展

在 `ScheduledItemSource` 中已有 `PLAN` 和 `AGENT`，任务自动展开的实例使用 `AGENT`（通过 Agent 工具创建）或通过 Web 创建时使用新的源类型。这里统一使用 `"task"` 作为新的源类型。

在 `ScheduledItemSource` 中新增：

```python
TASK = "task"
```

## 3. Alembic 迁移

生成迁移文件 `0010_task_enhancement_fields.py`，包含：

- 为 `task_items` 表新增字段：`schedule_type`、`start_date`、`end_date`、`duration_days`、`time_type`、`scheduled_time`、`scheduled_end_time`、`completed_days`
- 为 `scheduled_items` 表的 `source` 字段新增 `"task"` 枚举值（不需要 DDL 变更，因为是 String 类型）
- 向下迁移：删除新增字段

所有字段均为 `nullable=True` 带默认值，现有行不受影响。

## 4. 后端服务层

### 4.1 TaskService 扩展

**文件**：`backend/app/services/task_service.py`

新增方法：

```python
def generate_scheduled_items_for_task(
    self,
    user_id: str,
    task: TaskItem,
    exclude_dates: set[date] | None = None,
    timezone: str = "Asia/Shanghai",
) -> list[ScheduledItem]:
    """为任务生成日期范围内的所有 ScheduledItem。
    
    根据 schedule_type 计算出需要排期的日期列表。
    对每个日期：
    - fixed：按 scheduled_time/scheduled_end_time 创建
    - flexible：查找当天无冲突的空闲时段
    已存在的 ScheduledItem 不会被重复创建。
    """

def get_scheduled_items_for_task(
    self, user_id: str, task_id: str
) -> list[ScheduledItem]:
    """获取任务关联的所有非删除状态的 ScheduledItem。"""

def sync_task_changes_to_scheduled_items(
    self,
    task: TaskItem,
    changes: dict[str, Any],
    user_id: str,
) -> list[ScheduledItem]:
    """当任务标题、时长、时间段变化时，同步更新所有关联的 ScheduledItem。
    
    仅同步非排期属性（标题、描述）。
    如果 estimated_minutes/scheduled_time 变化，重算所有 ScheduledItem 的起止时间。
    """

def resolve_conflict_for_scheduled_item(
    self,
    user_id: str,
    item: ScheduledItem,
    source_task: TaskItem,
) -> ScheduledItem | None:
    """为冲突的 ScheduledItem 重新排程到下一个无冲突时段。
    
    仅在 time_type=flexible 时自动重排。
    fixed 时间冲突时返回 None，由调用方决定是否标记冲突。
    """

def _get_dates_for_task(self, task: TaskItem) -> list[date]:
    """根据 schedule_type 计算出需要排期的日期列表。"""

def _find_next_free_slot(
    self,
    user_id: str,
    plan_date: date,
    duration_minutes: int,
    existing_items: list[ScheduledItem],
    timezone: str = "Asia/Shanghai",
) -> tuple[datetime, datetime] | None:
    """在指定日期查找下一个无冲突的空闲时段。
    
    搜索范围：8:00 - 22:00
    从最早时间开始扫描，遇到第一个能容纳 duration_minutes 的间隙即返回。
    """

def complete_task_day(self, task: TaskItem) -> TaskItem:
    """标记任务的一天完成（completed_days += 1）。"""
```

### 4.2 ScheduledItemService 扩展

**文件**：`backend/app/services/scheduled_item_service.py`

新增方法：

```python
def list_by_task_id(
    self, user_id: str, task_id: str
) -> list[ScheduledItem]:
    """根据 source_task_id 获取任务关联的所有排期。"""

def batch_update_by_task_id(
    self,
    user_id: str,
    task_id: str,
    **changes: Any,
) -> int:
    """批量更新某任务关联的所有 ScheduledItem。返回更新数量。"""

def regenerate_scheduled_item_times(
    self,
    user_id: str,
    task: TaskItem,
) -> list[ScheduledItem]:
    """重算某任务关联的所有 ScheduledItem 的时间段（冲突重排）。"""
```

### 4.3 ConflictService 扩展

**文件**：`backend/app/services/conflict_service.py`

无需新增方法，已有的 `detect_item_conflicts` 和 `detect_day_conflicts` 可直接用于冲突检测。新增的排程逻辑在创建/更新 ScheduledItem 后调用已有方法检测冲突。

## 5. API 变更

### 5.1 现有 API 扩展

**`POST /api/tasks`** — 创建任务时支持新增字段

**`PATCH /api/tasks/{task_id}`** — 更新任务时：
- 如果修改了 `schedule_type`、`start_date`、`end_date`、`duration_days`、`time_type`、`scheduled_time`、`scheduled_end_time` 中的任何一个，触发重新生成/同步 ScheduledItem
- 同步逻辑：删除旧的 source_task_id 关联的 draft/active ScheduledItem（未完成且非 manual 创建的），重新调用 `generate_scheduled_items_for_task`

**`GET /api/tasks/{task_id}/scheduled-items`** — 新增端点，获取任务关联的所有 ScheduledItem

### 5.2 Schema 变更

**`backend/app/schemas/task.py`**：

```python
class TaskCreateRequest(BaseModel):
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str = "medium"
    # 新增
    schedule_type: str | None = None       # daily/weekdays/duration_days/custom_range
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    time_type: str | None = None           # fixed/flexible
    scheduled_time: time | None = None     # HH:MM
    scheduled_end_time: time | None = None # HH:MM

class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str | None = None
    # 新增
    schedule_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    time_type: str | None = None
    scheduled_time: time | None = None
    scheduled_end_time: time | None = None

class TaskItemDTO(BaseModel):
    id: str
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str
    status: str
    # 新增
    schedule_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    time_type: str | None = None
    scheduled_time: time | None = None
    scheduled_end_time: time | None = None
    completed_days: int | None = None
```

## 6. Agent 工具变更

### 6.1 CreateTaskArgs 扩展

**`backend/app/tools/schemas.py`**：

```python
class CreateTaskArgs(BaseModel):
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    deadline: datetime | None = None
    priority: str = Field(default="medium")
    # 新增
    schedule_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    time_type: str | None = None
    scheduled_time: str | None = None     # "14:00"
    scheduled_end_time: str | None = None # "15:00"
```

### 6.2 UpdateTaskArgs 扩展

同样新增 schedule_type、start_date 等字段。

### 6.3 create_task 工具 handler

在 `backend/app/tools/registry.py` 的 `create_task` handler 中：

- 创建任务后，如果有 schedule_type 和日期范围，自动调用 `generate_scheduled_items_for_task`
- 每个生成的 ScheduledItem 调用冲突检测

### 6.4 新增工具：regenerate_task_scheduled_items

```python
class RegenerateTaskScheduledItemsArgs(BaseModel):
    task_id: str
```

处理函数：根据任务最新配置重新生成所有 ScheduledItem。

## 7. 核心算法

### 7.1 日期计算

```
daily:          start_date 到 end_date（或 deadline 日期），每天
weekdays:       start_date 到 end_date（或 deadline 日期），仅周一到周五
duration_days:  start_date 起连续 duration_days 天
custom_range:   start_date 到 end_date
```

如果未设 `start_date`，默认为今天。如果 `daily`/`weekdays` 未设 `end_date` 但设了 `deadline`，使用 deadline 日期作为 end_date。

### 7.2 固定时间排程

```
for each date in dates:
    start = datetime(date.year, date.month, date.day) + scheduled_time
    end = datetime(date.year, date.month, date.day) + scheduled_end_time
    create ScheduledItem(start, end)
    检测冲突 → 如有冲突，记录冲突但不自动修改
```

### 7.3 弹性时间排程

```
for each date in dates:
    slot = find_next_free_slot(date, estimated_minutes)
    if slot found:
        create ScheduledItem(slot.start, slot.end)
        检测冲突（理论上无冲突）
    else:
        # 当天无足够空闲时段，跳过
        记录跳过原因
```

### 7.4 冲突重排

当某个 ScheduledItem 被检测到冲突时：

```
if task.time_type == "flexible":
    new_slot = find_next_free_slot(date, estimated_minutes, 排除当前 item)
    if new_slot found:
        更新 ScheduledItem 时间
    else:
        标记为冲突，保留原时间
else:
    # fixed 时间不自动重排，由用户决定
    记录冲突
```

### 7.5 同步修改

当任务的以下字段变化时：

- **标题/描述** → 直接批量更新所有关联 ScheduledItem 的 title/description
- **estimated_minutes / scheduled_time / scheduled_end_time** → 重新计算所有 ScheduledItem 的起止时间，弹性时间重新排程

## 8. 前端设计

### 8.1 任务页面 — 创建/编辑表单

在 `web/app/dashboard/tasks/page.tsx` 中：

**创建任务弹窗**（Modal Form）：

- 标题（必填）
- 描述（可选）
- 预估时长（分钟，可选）
- 优先级（低/中/高）
- 截止日期（可选）

**日期范围设置**（可选区域）：

- 重复类型：每天 / 工作日 / 持续N天 / 自定义区间
- 每天：设置开始日期和截止日期（可选，默认无限期）
- 工作日：设置开始日期和截止日期
- 持续N天：设置开始日期和天数
- 自定义区间：设置开始日期和结束日期

**时间设置**（可选区域）：

- 时间模式：固定时间 / 弹性时间
- 固定时间：开始时间 + 结束时间（或时长自动计算结束时间）
- 弹性时间：预估时长（分钟）

**编辑任务**：

- 点击任务卡片上的编辑按钮打开编辑弹窗
- 修改后自动触发 ScheduledItem 同步

### 8.2 任务卡片增强

任务列表中：

- 显示日期范围标签（如"每天 6/1-6/30"）
- 显示时间模式标签（"固定 14:00-15:00"或"弹性 60分钟"）
- 显示已完成天数（如"3/10天"）

### 8.3 前端类型更新

`web/lib/dashboard.ts`：

```typescript
export type TaskItem = {
  id: string;
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  deadline?: string | null;
  priority: string;
  status: string;
  // 新增
  schedule_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  time_type?: string | null;
  scheduled_time?: string | null;
  scheduled_end_time?: string | null;
  completed_days?: number | null;
};

export type TaskCreatePayload = {
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  deadline?: string | null;
  priority?: string;
  // 新增
  schedule_type?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number | null;
  time_type?: string | null;
  scheduled_time?: string | null;
  scheduled_end_time?: string | null;
};
```

新增 API 函数：

```typescript
export async function loadTaskScheduledItems(
  taskId: string,
  accessToken?: string
): Promise<ScheduledItem[]> {
  return requestJson<{ items: ScheduledItem[] }>(
    `/api/tasks/${taskId}/scheduled-items`,
    {},
    accessToken,
  ).then(r => r.items);
}

export async function regenerateTaskScheduledItems(
  taskId: string,
  accessToken?: string,
): Promise<ScheduledItem[]> {
  return requestJson<{ items: ScheduledItem[] }>(
    `/api/tasks/${taskId}/scheduled-items/regenerate`,
    { method: "POST" },
    accessToken,
  ).then(r => r.items);
}
```

## 9. 测试计划

### 9.1 后端单元测试

- 日期计算：daily / weekdays / duration_days / custom_range
- 固定时间排程：生成正确时间段的 ScheduledItem
- 弹性时间排程：找到空闲时段，跳过无空闲时段
- 冲突重排：flexible 自动重排，fixed 不重排
- 同步修改：标题变化同步、时长变化重算时间
- 数据隔离：user_id 隔离验证

### 9.2 集成测试

- 创建带日期范围的任务 → 验证 ScheduledItem 生成
- 更新任务时长 → 验证 ScheduledItem 时间同步
- 任务完成 → 验证 ScheduledItem 联动
- 删除任务 → 验证 ScheduledItem 软删除

### 9.3 现有测试兼容性

所有新增字段为 nullable，现有 `test_agent_debug_flow.py` 不受影响。

## 10. 边界情况

1. **无限期 daily**：未设 end_date 和 deadline 的 daily 任务，默认生成未来 7 天的 ScheduledItem（可配置），避免无限生成
2. **跨天 ScheduledItem**：scheduled_end_time < scheduled_time 时视为次日结束（如 23:00-01:00）
3. **已完成任务修改**：completed 状态的任务不允许修改 schedule_type，但允许修改标题/描述
4. **删除任务**：软删除任务时，关联的所有 ScheduledItem 标记为 deleted（不物理删除）
5. **时区**：所有时间基于用户 default_timezone，ScheduledItem 存储 UTC

## 11. 同源逻辑同步

修改一处逻辑后，需同步检查：

| 逻辑类型 | 同步位置 |
| -------- | -------- |
| schedule_type 枚举 | models/enums.py, schemas/task.py, 前端常量 |
| time_type 枚举 | models/enums.py, schemas/task.py, 前端常量 |
| 任务 DTO 字段 | schemas/task.py, 前端 TaskItem 类型 |
| 权限规则 | FastAPI dependency, 前端路由守卫 |
| 时间规则 | Agent Prompt, 后端时间工具, 前端展示组件 |
