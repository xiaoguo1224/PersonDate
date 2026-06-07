# 测试全面修复方案

## 背景

`0009_scheduled_items_unification.py` 迁移执行后，`calendar_events`、`day_plans`、`plan_items` 三张表被删除，统一为 `scheduled_items` 表。但后端代码有 6 个服务/路由文件仍引用已不存在的模型，测试基础设施仍使用 SQLite 且无法通过收集阶段。

## 范围

- 删除死代码（6 个文件 + 2 个 schema）
- 重写 conftest.py 连接 Docker PostgreSQL
- 修复全部 80+ 个测试到全绿
- 确认前端无依赖遗留问题

## Phase 1：删除死代码

### 删除文件

| 文件 | 原因 |
|------|------|
| `app/services/calendar_event_service.py` | 引用已删除的 `CalendarEvent` |
| `app/services/day_plan_service.py` | 引用已删除的 `DayPlan`、`PlanItem` |
| `app/services/plan_item_service.py` | 依赖 `DayPlanService`（已删除） |
| `app/api/routes/calendar_events.py` | `/api/calendar-events` 端点已过时 |
| `app/api/routes/day_plans.py` | `/api/day-plans` 端点已过时 |
| `app/api/routes/plan_items.py` | `/api/plan-items` 端点已过时 |
| `app/schemas/schedule.py` | 仅被 `calendar_events.py` 引用 |
| `app/schemas/plan.py` | 仅被 `day_plans.py`、`plan_items.py` 引用 |

### 验证方式

删除后 `uv run uvicorn app.main:app` 能正常启动，`uv run pytest --collect-only` 全部收集成功。

## Phase 2：PG 测试基础设施

### 架构

```
pytest 启动
  ↓ [session 级]
连接 postgres DB → CREATE DATABASE schedule_agent_test
  ↓ [session 级]
alembic upgrade head (在 test DB 上运行)
  ↓ [每个 test 函数]
新建连接 → 开启事务 → 注入 db_session → 测试执行 → 事务回滚 → 关闭连接
  ↓ [pytest 结束]
DROP DATABASE schedule_agent_test
```

### conftest.py Fixtures

| Fixture | 说明 |
|---------|------|
| `_test_db` | session 级，创建/销毁 `schedule_agent_test`，运行迁移 |
| `db_session` | 提供 PG 绑定 session，function 级自动回滚 |
| `app` | 最小 FastAPI 实例（不含 lifespan，避免 scheduler 干扰） |
| `client` | TestClient，`get_db` 已 override |
| `owner` | 已创建的 owner 用户对象 |
| `admin_token` | admin 的 JWT token |
| `member` | 已创建的 member 用户对象 |
| `member_token` | member 的 JWT token |

### 技术要点

- 使用 `isolation_level="AUTOCOMMIT"` 执行 `CREATE DATABASE`（PostgreSQL 要求）
- test 数据库独立于开发库 `schedule_agent_test`
- 每个测试的事务通过 `transaction.rollback()` 回滚，互不干扰
- `app` fixture 使用 `FastAPI()` + `include_router(api_router)`，不含 lifespan

## Phase 3：修复测试文件

### Sub-phase 3a：核心阻塞修复

| 测试文件 | 变更 |
|---------|------|
| `test_agent_debug_flow.py` | `CalendarEvent` → `ScheduledItem`；`DayPlan` 改为通过 `ScheduledItem.status` 判断；`Reminder.target_type` 从 `"event"` 改为 `"scheduled_item"` |
| `test_calendar_events_route.py` | 全部端点从 `/api/calendar-events` 改为 `/api/scheduled-items`，使用 `ScheduledItem` schemas |
| `test_plan_items_route.py` | 重写为 `scheduled_items` 的 create/update/complete/delete CRUD + generate/confirm 流程 |
| `test_conflicts_route.py` | 创建日程的端点从 `/api/calendar-events` 改为 `/api/scheduled-items`，冲突检测逻辑不变 |

### Sub-phase 3b：迁移 12 个测试到 conftest

使用 `client`、`admin_token`、`member_token` 等 conftest fixture，删除各文件内联的 SQLite 引擎创建和 `dependency_overrides` 模板代码。

涉及文件：`test_admin_users.py`、`test_agent_debug_route.py`、`test_me_settings.py`、`test_system_settings.py`、`test_tasks_route.py`、`test_web_agent_message_route.py`、`test_wechat_inbound.py`、`test_wechat_outbound.py`、`test_wechat_login_sessions.py`、`test_wechat_channel_management.py`、`test_wechat_channel_adapter.py`、`test_health_and_auth.py`

保留自有 setup 的文件（测试基础设施复杂，不强制改造）：`test_wechat_channel_qr_routes.py`、`test_wechat_channel_app.py`、`test_wechat_channel_poller.py`、`test_reminder_worker.py`、`test_daily_notification.py`、`test_scheduler_startup.py`、`test_ilink_client.py`、`test_llm_client.py`

## Phase 4：运行与迭代

### 执行顺序

```
Phase 1 删除死代码
  ↓ 验证：uv run pytest --collect-only 全部收集成功 + uv run uvicorn 正常启动
Phase 2 conftest 就绪
  ↓ 验证：uv run pytest tests/test_health_and_auth.py -v 通过
Phase 3a 修复 4 个阻塞测试
  ↓ 验证：uv run pytest -v 通过
Phase 3b 迁移 12 个测试
  ↓ 验证：uv run pytest -v 全绿
```

### 兜底策略

每次运行 `uv run pytest -v` 后对每个失败：
1. 定位测试文件和断言行
2. 分析原因（字段不匹配 / 路由返回码 / 语义变化）
3. 报告用户确认后修复
4. 重新运行直到全绿

### 验收标准

- `uv run pytest` 全部 80+ 个测试通过
- `uv run uvicorn app.main:app` 服务正常启动

## 前端确认结果

前端已正确使用 `ScheduledItem` 类型和 `/api/scheduled-items` 端点。旧函数名（`loadCalendarEvents`、`loadDayPlan`、`createPlanItem` 等）在 `dashboard.ts` 中均为空存根，未被任何页面 import。前端无需修复。
