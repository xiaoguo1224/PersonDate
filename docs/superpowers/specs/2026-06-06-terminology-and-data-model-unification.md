# 术语与数据模型统一设计

## 1. 问题分析

### 1.1 现状

当前系统在用户侧暴露了多个重叠的概念：

| 用户可见术语 | 对应数据表 | 含义 | 问题 |
|------------|-----------|------|------|
| 日程 | `calendar_events` | 固定起止时间的事件 | 与"安排"含义重叠 |
| 安排 | — | 尝试作为总称 | 宽泛，与"日程""计划项"边界模糊 |
| 计划 | `day_plans` | 每日排程方案 | 用户侧不需要区分"计划"与"安排" |
| 安排项 | `plan_items` | 计划中的具体条目 | 本质就是"安排"，不应独立存在 |
| 待办/任务 | `task_items` | 无固定时间的事项 | 唯一含义清晰的概念 |
| 安排草案 | — | 等待确认的初版计划 | 状态概念，不应独立成用户术语 |

与此同时，数据层有 4 张表服务同一个业务域，导致：

- 前端今日页区分"安排"（蓝）和"安排项"（青），展示割裂
- 日历页用两套 API 加载两套数据，有两套 CRUD 弹窗
- Agent 工具同时操作 `calendar_events` 和 `plan_items`，逻辑分散
- 冲突检测同时引用两种条目
- 提醒系统同时引用 `calendar_events` 和 `plan_items`

### 1.2 根因

数据模型设计时按"来源"分表（用户创建 vs 计划生成），但用户感知中它们都是"时间轴上的一条"，不应该按来源区分。

## 2. 目标

- **用户侧精简为 2 个概念**：安排（有固定时间）和任务（无固定时间）
- **数据层合并为 2 张主表**：`scheduled_items`（统一存放所有时间轴上条目）和 `tasks`
- **前端不再按来源区分条目类型**

## 3. 概念定义

| 概念 | 定义 | 示例 | 数据表 |
|------|------|------|--------|
| 安排 | 有固定开始和结束时间的事项 | 下午 3 点开会、10 点写论文 | `scheduled_items` |
| 任务 | 要做的事，有预计耗时但未定时间 | 写完论文、整理资料 | `tasks` |
| 今日安排 | 首页标题，指今日时间轴上的安排 | — | 查询视图 |

取消以下用户侧术语：日程、计划、计划项、安排草案、安排项、待办（统一用"任务"）。

## 4. 数据模型

### 4.1 scheduled_items（新增，替代 calendar_events + day_plans + plan_items）

```sql
CREATE TABLE scheduled_items (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    location VARCHAR(255),
    source VARCHAR(32) NOT NULL DEFAULT 'manual',
        -- 'manual': 用户直接创建
        -- 'agent': Agent 创建
        -- 'plan': 计划生成（源自任务排程）
    source_task_id UUID REFERENCES tasks(id),
        -- 如果源自某个任务，记录关联
    remind_before_minutes INTEGER,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
        -- 'draft': 草稿（待确认）
        -- 'active': 已确认
        -- 'completed': 已完成
        -- 'cancelled': 已取消
        -- 'deleted': 软删除
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_end_after_start CHECK (end_time > start_time)
);

CREATE INDEX idx_scheduled_items_user_time
    ON scheduled_items(user_id, start_time);
CREATE INDEX idx_scheduled_items_user_status
    ON scheduled_items(user_id, status);
CREATE INDEX idx_scheduled_items_source_task
    ON scheduled_items(source_task_id);
CREATE INDEX idx_scheduled_items_date
    ON scheduled_items((start_time::date));
```

设计要点：
- 不再需要 `day_plans` 表：某天的安排 = `start_time` 落在此日的所有 `scheduled_items`
- 不再需要 `plan_items` 表：所有时间轴条目统一存放
- "安排草案" = status='draft' 的安排，确认 = 批量改状态为 'active'
- `source_task_id` 记录安排是否源自某个任务，支持任务到安排的关联查询
- 不保留 `repeat_rule`、`external_calendar_*` 等暂未使用的字段，需要时再加

### 4.2 tasks（替代 task_items，精简）

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    estimated_minutes INTEGER,
    deadline TIMESTAMPTZ,
    priority VARCHAR(32) NOT NULL DEFAULT 'medium',
        -- 'low', 'medium', 'high', 'urgent'
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
        -- 'pending': 待处理
        -- 'in_progress': 进行中
        -- 'completed': 已完成
        -- 'cancelled': 已取消
        -- 'deleted': 软删除
    source VARCHAR(32) NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_estimated_minutes CHECK (estimated_minutes IS NULL OR estimated_minutes > 0)
);

CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_user_deadline ON tasks(user_id, deadline);
```

移除 `task_items.status` 中的 `planned` 值。任务不再有"已排入计划"状态——判断一个任务是否已排入当天，只需查 `scheduled_items.source_task_id`。

### 4.3 schedule_conflicts（保留，引用改为 scheduled_item_id）

```sql
-- related_item_ids JSONB 改为明确字段：
-- conflict_item_id UUID FK → scheduled_items.id
-- conflict_with_item_id UUID FK → scheduled_items.id
```

### 4.4 reminder_jobs（保留，引用改为 scheduled_items）

```sql
-- target_type: 只保留 'scheduled_item'
-- target_id: 引用 scheduled_items.id
```

### 4.5 删除的表

- `calendar_events` → 迁移到 `scheduled_items`
- `day_plans` → 不再需要
- `plan_items` → 迁移到 `scheduled_items`

## 5. API 变化

### 5.1 安排 API（合并原有 calendar-events + plan-items + day-plans）

```
POST   /api/scheduled-items              # 创建安排
GET    /api/scheduled-items              # 查询安排（支持 date、keyword 参数）
PATCH  /api/scheduled-items/{id}         # 修改安排
DELETE /api/scheduled-items/{id}         # 删除安排
PATCH  /api/scheduled-items/{id}/complete  # 标记完成

POST   /api/scheduled-items/generate     # 为某日生成安排草案（替代 /day-plans/{date}/generate）
POST   /api/scheduled-items/confirm      # 确认某日所有 draft 安排
POST   /api/scheduled-items/regenerate   # 重新为某日生成安排
```

### 5.2 任务 API（基本不变）

```
POST   /api/tasks
GET    /api/tasks
PATCH  /api/tasks/{id}
DELETE /api/tasks/{id}
PATCH  /api/tasks/{id}/complete
```

### 5.3 冲突 API（引用字段更新）

```
GET    /api/conflicts
POST   /api/conflicts/detect
```

### 5.4 已废弃的 API

- `POST/PATCH/DELETE /api/calendar-events/*` → 由 `/api/scheduled-items` 替代
- `GET/POST /api/day-plans/*` → 由 `/api/scheduled-items` 替代
- `POST/PATCH/DELETE /api/plan-items/*` → 由 `/api/scheduled-items` 替代

## 6. Agent 工具变化

### 6.1 工具重命名

| 旧工具 | 新工具 |
|-------|--------|
| `create_event` | `create_scheduled_item` |
| `query_events` | `query_scheduled_items` |
| `update_event` | `update_scheduled_item` |
| `delete_event` | `delete_scheduled_item` |
| `search_event_candidates` | 取消，`query_scheduled_items` 通过 keyword 参数覆盖 |
| `create_task` | 保留 |
| `query_tasks` | 保留 |
| `update_task` | 保留 |
| `complete_task` | 保留 |
| `analyze_day` | 保留，改为查询 `scheduled_items` |
| `find_free_slots` | 保留，改为查询 `scheduled_items` |
| `plan_tasks_into_day` | 保留，逻辑改为创建 `scheduled_items` |
| `confirm_plan` | 保留，改为确认 `scheduled_items` |
| `regenerate_plan` | 保留 |
| `detect_conflicts` | 保留，引用改为 `scheduled_items` |
| `suggest_reschedule` | 保留 |

### 6.2 AgentState 变化

```
candidate_events → candidate_scheduled_items
events           → scheduled_items
draft_plan       → 取消（draft 体现在 scheduled_items.status）
```

### 6.3 Agent Prompt 文案更新

- `main.py`: FastAPI title "微信智能日程规划 Agent" → "微信智能安排规划 Agent"
- `parsing.py` `infer_event_title()`: fallback 返回值 `or "日程"` → `or "安排"`
- `parsing.py` `infer_task_title()`: fallback 返回值 `or "任务"` 保留
- `graph.py` 中 `_candidate_line()` 等辅助函数的"日程"文案 → "安排"
- 冲突描述模板："日程冲突" → "安排冲突"；"调整日程时间" → "调整安排时间"

注意：`SchedulePlanningGraph` 类名、`graph.py` 文件名、`agents/` 目录结构等内部工程命名不做修改。

### 6.4 意图分类变化

```
create_event  → create_scheduled_item
update_event  → update_scheduled_item
delete_event  → delete_scheduled_item
query_events  → query_scheduled_items
plan_day      → 保留
create_task   → 保留
confirm_plan  → confirm_scheduled_items
```

## 7. 前端变化

### 7.1 今日页（/dashboard/today）

- 时间轴：不再按 kind="event" / kind="plan_item" 区分展示
- 所有条目统一数据类型 `ScheduledItem`
- 标签统一为"安排"，不再分蓝色/青色
- "计划完成度" → "今日完成度"
- 待办区：筛掉已生成安排的任务（有 scheduled_items.source_task_id = task.id 且日期为今日）

### 7.2 日历页（/dashboard/calendar）

- 去掉 DayPlan 相关的加载和 CRUD
- 只加载一套 API：`GET /api/scheduled-items?start_time=...&end_time=...`
- 弹窗/表单统一使用 ScheduledItem 类型
- 不再有两套弹窗（CalendarEventForm / PlanItemForm）

### 7.3 任务池页（/dashboard/tasks）

- 列出所有 tasks，每个任务显示是否有已生成的安排
- 可以在任务列表直接"排入今日"（创建 scheduled_item）

### 7.4 冲突页（/dashboard/conflicts）

- 引用字段改为 `scheduled_item_id`，文案从"日程冲突"改为"安排冲突"

### 7.5 菜单

- "今日安排" → 保留
- "待办" → "任务"

## 8. 数据迁移

### 8.1 迁移策略

采用 Alembic 迁移，支持正向回退：

1. 创建 `scheduled_items` 表
2. 从 `calendar_events` 迁移数据到 `scheduled_items`
3. 从 `plan_items` 迁移数据到 `scheduled_items`
4. 迁移 `schedule_conflicts` 的引用
5. 迁移 `reminder_jobs` 的引用
6. 重命名 `task_items` → `tasks`
7. 删除 `calendar_events`、`day_plans`、`plan_items` 表

### 8.2 calendar_events → scheduled_items 映射

```
calendar_events.id           → scheduled_items.id
calendar_events.user_id      → scheduled_items.user_id
calendar_events.title        → scheduled_items.title
calendar_events.description  → scheduled_items.description
calendar_events.start_time   → scheduled_items.start_time
calendar_events.end_time     → scheduled_items.end_time
calendar_events.timezone     → scheduled_items.timezone
calendar_events.location     → scheduled_items.location
calendar_events.source       → scheduled_items.source
calendar_events.status       → scheduled_items.status（active/completed/cancelled/deleted 直接映射，无 draft）
calendar_events.created_by_channel → 标识渠道
                              → scheduled_items.source_task_id = NULL
                              → scheduled_items.remind_before_minutes = 从 reminder_jobs 回填
```

### 8.3 plan_items → scheduled_items 映射

注意：plan_items 有 `day_plan_id`，需要通过 `day_plans.status` 判断来源计划的确认状态。

```
plan_items.id                → scheduled_items.id
plan_items.user_id           → scheduled_items.user_id
plan_items.title             → scheduled_items.title
plan_items.start_time        → scheduled_items.start_time
plan_items.end_time          → scheduled_items.end_time
                              → scheduled_items.timezone = 用户默认时区
plan_items.is_flexible       → 不再需要
plan_items.sort_order        → scheduled_items.sort_order
plan_items.ref_id + item_type→ scheduled_items.source_task_id（当 item_type='task' 时）
                              → scheduled_items.source = 'plan'

plan_items.status 映射规则（需查阅关联的 day_plans.status）：
  - day_plans.status = 'draft' 且 plan_items.status = 'planned'
    → scheduled_items.status = 'draft'
  - day_plans.status IN ('confirmed', 'active') 且 plan_items.status = 'planned'
    → scheduled_items.status = 'active'
  - plan_items.status = 'in_progress'  → 'in_progress'
  - plan_items.status = 'completed'    → 'completed'
  - plan_items.status = 'cancelled'    → 'cancelled'
  - plan_items.status = 'skipped'      → 'cancelled'
```

### 8.4 day_plans 迁移

`day_plans` 表整体废弃。确认/草稿状态通过 `scheduled_items.status = 'draft'` 体现。

### 8.5 task_items → tasks 迁移

`task_items` 表结构基本保留，主要变化是移除 `status` 中 `planned` 值，因此：

- 现有 `status = 'planned'` 的任务 → `status = 'pending'`
- 表通过 `ALTER TABLE task_items RENAME TO tasks` 重命名，后续通过迁移脚本删除 `planned` 的 CHECK 约束

迁移后，判断一个任务是否"已排入安排"的逻辑改为：查询 `scheduled_items.source_task_id = task.id`。

### 8.6 schedule_conflicts 迁移

`related_item_ids` JSONB 中的 `current` 和 `other` key 指向的 ID，从 `calendar_events.id` 或 `plan_items.id` 映射为对应的 `scheduled_items.id`。

冲突标题和描述中的"日程"文案统一改为"安排"。

### 8.7 reminder_jobs 迁移

- `target_type = 'calendar_event'` → `target_type = 'scheduled_item'`
- `target_type = 'plan_item'` → `target_type = 'scheduled_item'`
- `target_id` 更新为对应的 `scheduled_item.id`

## 9. 测试策略

- 所有已有测试需要更新断言（数据库表名、API 路径、字段名）
- Agent 测试用例中 `create_event` 意图改为 `create_scheduled_item`
- 新增迁移测试：验证数据从旧表到新表的完整性
- 前端测试：取消 plan_item 相关测试，统一为 scheduled_item

## 10. 实施顺序

```
1. 创建 scheduled_items 表 + Alembic 迁移
2. 数据迁移脚本（从 calendar_events / plan_items / day_plans 迁移）
3. 重构 Service 层
4. 重构 API 路由层
5. 重构 ToolRegistry 和 Agent 工具
6. 重构 Graph 节点（AgentState、意图、处理函数）
7. Agent Prompt 更新
8. 前端 API 层重构（API 调用、类型定义）
9. 前端页面重构（今日页、日历页、任务页）
10. 删除旧表和废弃代码
11. 全链路测试
```

## 11. 弃用与兼容

- 旧 API 路径（`/api/calendar-events`、`/api/day-plans`、`/api/plan-items`）在新版上线后立即移除，不保留兼容
- 旧表在迁移验证完成后删除
- 数据迁移为一次性操作，不回退
