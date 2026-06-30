---
name: task-scheduled-reminder-grouping-design
description: 任务排期提醒补齐与提醒页折叠展示设计
---

# 任务排期提醒补齐与提醒页折叠展示设计

## 1. 概述

本次需求包含两个相关但边界清晰的改动：

1. 通过任务创建或确认生成的排期，必须同步生成并维护对应提醒。
2. 提醒页对“同一任务、同一提醒时刻”的多天提醒做前端折叠展示，但后端仍按每天一条提醒记录存储。

当前系统存在两个缺口：

- `TaskService.sync_task_to_scheduled_items(...)` 负责把任务展开成多天 `ScheduledItem`，但没有同步维护对应 `ReminderJob`。
- `ScheduledItemService.confirm_drafts_for_date(...)` 只把草稿状态改成 `active`，没有在确认时批量补建提醒。
- 提醒页 `web/app/dashboard/reminders/page.tsx` 按单条提醒逐条渲染，缺少“同任务同时间多天提醒”的折叠视图。

本设计目标是让“任务排期”和“提醒”成为一致同步的数据，并将折叠逻辑限制在前端展示层，避免改变后端存储语义。

## 2. 目标与非目标

### 2.1 目标

- 覆盖以下 3 条链路的提醒自动维护：
  - 任务页创建/编辑任务后自动生成的排期
  - 任务页重新生成排期
  - Agent 生成草案后，用户确认转正的排期
- 排期新增、修改、删除时，对应提醒同步新增、更新、取消。
- 任务排期提醒默认使用 `ScheduledItem.remind_before_minutes`，其默认值来自用户设置 `default_remind_before_minutes`。
- 提醒页仅做前端折叠展示，不改变“每天一条提醒”的后端存储模型。
- 折叠后仍支持进入组内，对单天提醒单独调整、取消、重新激活。

### 2.2 非目标

- 不做后端批量提醒记录合并。
- 不增加批量取消、批量调整提醒的能力。
- 不修改 Reminder Worker 的发送语义。
- 不修改微信通道行为。

## 3. 现状与问题

### 3.1 任务排期链路

`backend/app/api/routes/tasks.py` 在创建或更新任务后，会调用 `TaskService.sync_task_to_scheduled_items(task, user_id)` 生成或重建排期，但当前链路没有同时维护提醒，因此任务排期生成后提醒页不完整。

### 3.2 草案确认链路

`backend/app/agent/tools.py` 中的 `confirm_plan(plan_date)` 调用 `ScheduledItemService.confirm_drafts_for_date(user_id, plan_date)` 将草稿排期转为 `active`。当前该服务只更新状态，不生成提醒，因此 Agent 确认后的任务排期也没有提醒。

### 3.3 提醒页分组能力不足

提醒接口 `ReminderDTO` 当前只返回提醒自身字段和关联排期的 `original_time`、`remind_before_minutes`，没有稳定区分“这些提醒属于同一个任务”的字段。若前端仅按 `title` 折叠，会把不同任务但同名标题错误合并。

## 4. 设计决策

### 4.1 后端仍按每天一条提醒存储

不改变现有 `ReminderJob` 粒度。每个有效 `ScheduledItem` 最多对应一个当前生效的 pending 提醒。前端折叠只是一种展示聚合，不影响后端数据模型。

### 4.2 草稿阶段不创建可触发提醒

任务草稿在用户确认前不创建 pending 提醒，避免未确认草案进入提醒队列。只有草稿转 `active` 后，才批量生成提醒。

### 4.3 分组依赖稳定业务键

提醒页分组必须基于 `source_task_id`，而不是 `title`。因此提醒查询接口需要把关联排期上的 `source_task_id` 透传给前端。

## 5. 后端设计

### 5.1 ReminderDTO 扩展

文件：

- `backend/app/schemas/reminder.py`
- `backend/app/api/routes/reminders.py`

新增只读字段：

```python
source_task_id: str | None = None
```

来源规则：

- 当 `ReminderJob.target_type == "scheduled_item"` 且能加载到关联 `ScheduledItem` 时，返回 `scheduled_item.source_task_id`
- 其他提醒返回 `None`

该字段仅用于前端分组，不改变提醒触发逻辑。

### 5.2 新增提醒同步入口

文件：

- `backend/app/services/reminder_service.py`

新增一个围绕 `ScheduledItem` 的统一同步方法：

```python
def sync_pending_for_scheduled_item(
    self,
    *,
    user_id: str,
    item: ScheduledItem,
) -> ReminderJob | None:
    """根据 ScheduledItem 当前状态和提醒配置，同步唯一的 pending 提醒。"""
```

规则：

1. 若 `item.status != "active"`，取消该排期现有 pending 提醒，不创建新提醒。
2. 若 `item.remind_before_minutes is None`，取消该排期现有 pending 提醒，不创建新提醒。
3. 否则先取消该排期现有 pending 提醒，再基于当前 `start_time/title/remind_before_minutes` 创建一条新的 pending 提醒。
4. 该方法保证“一个排期最多一个当前生效 pending 提醒”。

保留现有 `create_for_target(...)` / `cancel_by_target(...)`，但业务层以后优先走 `sync_pending_for_scheduled_item(...)`，避免各入口散落重复逻辑。

### 5.3 任务排期同步链路补齐提醒

文件：

- `backend/app/services/task_service.py`

在 `sync_task_to_scheduled_items(task, user_id)` 中补齐以下行为：

1. 新建排期时：
  - 为每个生成的 `ScheduledItem` 写入 `remind_before_minutes`
  - 默认值取当前用户 `UserSettings.default_remind_before_minutes`
  - 若用户设置缺失，则显式写入 `0`，表示开始时提醒
2. 对保留并更新的排期：
  - 若标题、开始时间、提前提醒分钟数变化，调用 `ReminderService.sync_pending_for_scheduled_item(...)`
3. 对重生成过程中被删除、软删除或不再属于当前任务排期的旧排期：
  - 取消其对应 pending 提醒

这里的“更新提醒”不仅覆盖创建任务，也覆盖编辑任务、重新生成排期、排期时间变化。

### 5.4 草稿确认链路补齐提醒

文件：

- `backend/app/services/scheduled_item_service.py`
- `backend/app/agent/tools.py`
- `backend/app/api/routes/scheduled_items.py`

调整 `ScheduledItemService.confirm_drafts_for_date(user_id, plan_date)` 的返回值与职责：

```python
def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
    """将指定日期的 draft 排期改为 active，并返回这些已确认排期。"""
```

行为变更：

1. 查询指定日期内状态为 `draft` 的排期
2. 将这些排期状态改为 `active`
3. 返回这些排期对象，而不是仅返回数量

调用侧更新：

- Agent 工具 `confirm_plan(plan_date)` 中，在确认后对返回的每个排期调用 `ReminderService.sync_pending_for_scheduled_item(...)`
- Web 侧若有确认草稿入口，也走同一逻辑

这样可以保证“草稿不提醒，确认后补提醒”的行为稳定一致。

### 5.5 手动修改排期时同步修改提醒

文件：

- `backend/app/api/routes/scheduled_items.py`
- `backend/app/agent/tools.py`

现有更新排期时已经做了“取消旧提醒并重建新提醒”的一部分逻辑，但后续需要统一改为调用 `sync_pending_for_scheduled_item(...)`，避免多处重复。

触发时机：

- 修改 `start_time`
- 修改 `title`
- 修改 `remind_before_minutes`
- 修改 `status`

规则：

- 若改后排期仍是 `active` 且有有效 `remind_before_minutes`，则重建提醒
- 若改后排期不再可提醒，则取消提醒

### 5.6 删除或失效排期时取消提醒

以下场景均需取消该排期的 pending 提醒：

- 排期软删除
- 任务重生成导致某天排期被移除
- 任务排期配置被清空
- 排期状态从 `active` 变为 `draft`、`completed`、`deleted` 等非可提醒状态

## 6. 前端设计

### 6.1 ReminderItem 类型扩展

文件：

- `web/lib/dashboard.ts`

新增字段：

```typescript
source_task_id?: string | null;
```

前端仅用于折叠分组，不作为编辑参数提交。

### 6.2 折叠范围

文件：

- `web/app/dashboard/reminders/page.tsx`

只折叠以下提醒：

- `target_type === "scheduled_item"`
- `source_task_id` 非空

以下情况保持逐条显示：

- 手动日程提醒且没有 `source_task_id`
- 非 `scheduled_item` 提醒
- 测试提醒或其他未来扩展提醒类型

### 6.3 折叠条件

仅在同一页签数据集内，满足以下条件的提醒折叠为一组：

- `source_task_id` 相同
- `status` 相同
- `remind_before_minutes` 相同
- 触发时间的本地时钟值相同，例如都为 `08:00`

因此：

- 1/2/3/4/6 号均在 `08:00` 触发 -> 折叠为一组
- 其中一天改成 `10:00` -> 自动拆出单独显示，不进入 `08:00` 组

### 6.4 分组键

建议在前端用以下字段组合生成稳定分组键：

```text
source_task_id + status + remind_before_minutes + trigger_clock
```

其中 `trigger_clock` 以用户当前时区格式化后的 `HH:mm` 为准，确保按用户视角分组。

### 6.5 展示方式

提醒页将列表数据先转换为“展示节点”：

- 单条提醒节点
- 折叠组节点

折叠组默认展示：

- 任务标题
- 触发时间，如 `08:00`
- 日期数量，如 `5 天`
- 日期摘要，如 `1/2/3/4/6 号`
- 状态标签
- 提前提醒分钟数

用户展开后，看到组内每天的真实提醒记录。

### 6.6 交互边界

折叠组本身不提供批量操作，避免误操作扩大影响。

允许的操作放在组内单条提醒上：

- 调整提醒时间
- 取消提醒
- 重新激活

当用户修改组内某一天提醒后：

- 若触发时刻仍满足当前分组条件，则保留在组内
- 若改为不同时间，如 `08:00 -> 10:00`，刷新后自动拆组

## 7. 一致性与边界情况

### 7.1 默认提醒分钟数来源

任务生成的排期，其 `ScheduledItem.remind_before_minutes` 默认写入用户设置 `default_remind_before_minutes`。提醒生成永远以排期字段为准，而不是再次直接读取用户设置。

这样可保证：

- 生成后的某一天提醒可以单独调整
- 后续用户修改默认提醒设置，不会 retroactively 改写历史排期

### 7.2 重复提醒防护

所有入口统一通过 `sync_pending_for_scheduled_item(...)` 维护提醒，避免以下问题：

- 重生成排期后同一天出现两条 pending 提醒
- 修改排期后旧提醒未取消
- 草稿确认重复执行后重复建提醒

### 7.3 过期提醒

本次设计明确约束为：

- 若同步计算后的 `trigger_time <= now`，取消该排期现有 pending 提醒，且不再新建 pending 提醒。
- 对交互式“单条调整提醒时间”接口，继续保持现有校验，禁止把提醒调整到已过期时间。

这样可以避免任务重生成、草稿确认或排期修改时，意外补出一批已经过期的 pending 提醒。

## 8. 涉及文件

后端：

- `backend/app/schemas/reminder.py`
- `backend/app/api/routes/reminders.py`
- `backend/app/services/reminder_service.py`
- `backend/app/services/task_service.py`
- `backend/app/services/scheduled_item_service.py`
- `backend/app/api/routes/tasks.py`
- `backend/app/api/routes/scheduled_items.py`
- `backend/app/agent/tools.py`

前端：

- `web/lib/dashboard.ts`
- `web/app/dashboard/reminders/page.tsx`

测试：

- `backend/tests/test_reminder_service.py`
- `backend/tests/test_tasks_route.py`
- `backend/tests/test_agent_debug_flow.py`
- 视实际情况新增 reminders page 的前端单测或最小纯函数测试

## 9. 测试与验证

### 9.1 后端测试

至少覆盖：

1. 创建带日期范围和固定时间的任务后，生成多天排期，并为每天生成一条提醒
2. 更新任务排期时间后，对应提醒触发时间同步变化
3. 重新生成任务排期时，旧排期提醒被取消，新排期提醒正确生成
4. Agent 草稿确认后，为确认的排期批量生成提醒
5. 删除某天排期或移除任务排期配置后，对应提醒被取消
6. 同一排期不会出现多条 pending 提醒
7. 提醒查询接口返回 `source_task_id`

### 9.2 前端验证

至少覆盖：

1. 同一任务在多个日期、同一 `08:00` 触发时，提醒页折叠成一组
2. 其中一天改成 `10:00` 后，该条提醒自动拆组
3. 非任务提醒不会被错误折叠
4. 展开组后，仍可对单天提醒执行取消、调整、重新激活

### 9.3 构建与人工回归

实现阶段完成后执行：

- 后端相关测试
- `pnpm lint`
- `pnpm typecheck`
- 提醒页人工验证折叠、拆组、单条操作

## 10. 风险与取舍

### 10.1 接口扩展兼容性

给 `ReminderDTO` 增加 `source_task_id` 属于向后兼容扩展，风险较低。前端旧代码不读取该字段时不受影响。

### 10.2 任务服务职责增加

`TaskService` 会承担更多“排期 + 提醒同步”的职责，需避免把提醒逻辑散落在 route 或 agent tool 中。核心策略是把提醒维护统一收口到 `ReminderService.sync_pending_for_scheduled_item(...)`。

### 10.3 折叠只做展示

不做批量操作是一个有意取舍。它牺牲了一点操作效率，但能显著降低误取消、误改整组提醒的风险，也更符合“后端仍然按每天存储”的语义。
