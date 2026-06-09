# 旧逻辑残留清理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理项目中两次重大架构重构（OpenAI → LangChain/LangGraph、pending_state → interrupt）后残留的约 1,500 行死代码、兼容层和过时测试。

**Architecture:** 按依赖层自底向上分 4 次提交：先删死代码文件，再移除 pending_state 兼容层，再 DROP TABLE 清理 models，最后修复测试 mock。每批独立可验证。

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, LangGraph, pytest, Next.js, TypeScript

---

### Task 1: 删除死代码文件

**Files:**
- Delete: `backend/app/tools/__init__.py`
- Delete: `backend/app/tools/schemas.py`
- Delete: `backend/app/tools/registry.py`
- Delete: `backend/app/tools/executor.py`
- Delete: `backend/app/agent/schemas.py`
- Delete: `backend/app/agent/llm_client.py`
- Delete: `backend/app/agent/parsing.py`
- Delete: `backend/app/agent/state.py`
- Delete: `backend/app/services/pending_state_service.py`
- Delete: `backend/tests/test_llm_client.py`
- Modify: `backend/app/core/cache_invalidator.py:51-53`

- [ ] **Step 1: 删除 10 个死代码文件**

```bash
cd backend
rm -rf app/tools/
rm app/agent/schemas.py
rm app/agent/llm_client.py
rm app/agent/parsing.py
rm app/agent/state.py
rm app/services/pending_state_service.py
rm tests/test_llm_client.py
```

- [ ] **Step 2: 删除 cache_invalidator.py 中的死函数**

删除 `backend/app/core/cache_invalidator.py` 第 51-53 行的 `invalidate_pending_state()` 函数：

```python
# 删除以下内容：
def invalidate_pending_state(conversation_id: str) -> None:
    logger.info("失效 Agent pending state 缓存 conversation_id=%s", conversation_id)
    cache_delete(f"schedule:agent:pending:{conversation_id}")
```

- [ ] **Step 3: 验证无导入错误**

```bash
cd backend
uv run python -c "from app.agent.graph import SchedulePlanningGraph; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 运行 lint**

```bash
cd backend
uv run ruff check .
```

Expected: 无错误

- [ ] **Step 5: 运行测试（排除过时的集成测试）**

```bash
cd backend
uv run pytest tests/ --ignore=tests/test_agent_debug_flow.py -x -v
```

Expected: 通过（test_agent_debug_flow.py 依赖旧 FakeLLMClient，后续 Task 4 修复）

- [ ] **Step 6: 提交**

```bash
git add -A backend/app/tools/ backend/app/agent/schemas.py backend/app/agent/llm_client.py backend/app/agent/parsing.py backend/app/agent/state.py backend/app/services/pending_state_service.py backend/tests/test_llm_client.py backend/app/core/cache_invalidator.py
git commit -m "chore(agent): 删除重构后残留的死代码文件"
```

---

### Task 2: 移除 pending_state 兼容层

**Files:**
- Modify: `backend/app/agent/graph.py:21,380,453-474`
- Modify: `backend/app/schemas/agent.py:14`
- Modify: `backend/app/api/routes/agent.py:35`
- Modify: `web/lib/dashboard.ts:330`
- Modify: `web/app/dashboard/today/page.tsx:902`

- [ ] **Step 1: 修改 graph.py — 删除 pending_state 导入和构造逻辑**

删除第 21 行：
```python
from app.models.enums import PendingStateStatus, PendingStateType
```

删除第 453-466 行的 pending_state 构造逻辑：
```python
        # 从 graph 状态中提取 pending_state
        pending_state = None
        if result.get("needs_confirmation"):
            pending_state = {
                "type": PendingStateType.WAITING_GENERIC_CONFIRMATION.value,
                "confirmation_prompt": result.get("confirmation_prompt", ""),
                "status": PendingStateStatus.ACTIVE.value,
            }
        elif interrupts:
            pending_state = {
                "type": PendingStateType.WAITING_GENERIC_CONFIRMATION.value,
                "confirmation_prompt": result.get("confirmation_prompt", ""),
                "status": PendingStateStatus.ACTIVE.value,
            }
```

将返回值中的 `"pending_state": pending_state,` 改为 `"pending_state": None,`（第 474 行附近）。

- [ ] **Step 2: 修改 DebugMessageResponse schema**

删除 `backend/app/schemas/agent.py` 第 14 行：
```python
    pending_state: dict | None = None
```

- [ ] **Step 3: 修改 agent route**

删除 `backend/app/api/routes/agent.py` 第 35 行：
```python
        pending_state=result.get("pending_state"),
```

- [ ] **Step 4: 修改前端类型**

删除 `web/lib/dashboard.ts` 第 330 行：
```typescript
  pending_state?: Record<string, unknown> | null;
```

- [ ] **Step 5: 修改前端页面**

删除 `web/app/dashboard/today/page.tsx` 第 902 行：
```typescript
              result.pending_state ? "当前处于待处理状态" : null,
```

- [ ] **Step 6: 验证后端**

```bash
cd backend
uv run ruff check .
uv run python -c "from app.agent.graph import SchedulePlanningGraph; print('OK')"
```

Expected: 无错误

- [ ] **Step 7: 验证前端**

```bash
cd web
pnpm build
```

Expected: 构建成功

- [ ] **Step 8: 运行测试**

```bash
cd backend
uv run pytest tests/ --ignore=tests/test_agent_debug_flow.py -x -v
```

Expected: 通过

- [ ] **Step 9: 提交**

```bash
git add backend/app/agent/graph.py backend/app/schemas/agent.py backend/app/api/routes/agent.py web/lib/dashboard.ts web/app/dashboard/today/page.tsx
git commit -m "refactor(agent): 移除 pending_state 兼容层，统一使用 LangGraph interrupt"
```

---

### Task 3: DROP TABLE + 清理 models

**Files:**
- Create: `backend/alembic/versions/0010_drop_agent_pending_states.py`
- Modify: `backend/app/models/agent.py:37-53`
- Modify: `backend/app/models/enums.py:142-155`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建 migration 文件**

```bash
cd backend
uv run alembic revision --autogenerate -m "drop agent_pending_states table"
```

检查生成的 migration 文件，确保只包含 DROP TABLE 操作。如果 autogenerate 产生了多余的变更，手动编辑只保留 `op.drop_table("agent_pending_states")`。

- [ ] **Step 2: 手动编写 migration（如果 autogenerate 不可用）**

创建 `backend/alembic/versions/0010_drop_agent_pending_states.py`：

```python
"""drop agent_pending_states table

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("agent_pending_states")


def downgrade() -> None:
    op.create_table(
        "agent_pending_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.String(255), nullable=False),
        sa.Column("state_type", sa.String(64), nullable=False),
        sa.Column("state_payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pending_state_user_conversation_status", "agent_pending_states", ["user_id", "conversation_id", "status"])
    op.create_index("ix_pending_state_expires_at", "agent_pending_states", ["expires_at"])
```

注意：revision ID 和 down_revision 需要根据实际的最新 migration 调整。先用 `uv run alembic heads` 查看当前最新 revision。

- [ ] **Step 3: 删除 AgentPendingState ORM 模型**

删除 `backend/app/models/agent.py` 第 37-53 行的 `AgentPendingState` 类。

- [ ] **Step 4: 删除 PendingStateType 和 PendingStateStatus 枚举**

删除 `backend/app/models/enums.py` 第 142-155 行：
```python
class PendingStateType(StrEnum):
    WAITING_PLAN_CONFIRMATION = "waiting_plan_confirmation"
    WAITING_EVENT_SELECTION = "waiting_event_selection"
    WAITING_CONFLICT_RESOLUTION = "waiting_conflict_resolution"
    WAITING_CLARIFICATION = "waiting_clarification"
    WAITING_REMINDER_TIME = "waiting_reminder_time"
    WAITING_GENERIC_CONFIRMATION = "waiting_generic_confirmation"


class PendingStateStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"
    COMPLETED = "completed"
```

- [ ] **Step 5: 清理 models/__init__.py**

删除以下导入：
```python
from app.models.agent import AgentPendingState, AgentRunLog  # 改为只导入 AgentRunLog
```

改为：
```python
from app.models.agent import AgentRunLog
```

删除枚举导入中的 `PendingStateStatus` 和 `PendingStateType`。

删除 `__all__` 中的 `"AgentPendingState"`、`"PendingStateStatus"`、`"PendingStateType"`。

- [ ] **Step 6: 执行 migration**

```bash
cd backend
uv run alembic upgrade head
```

Expected: migration 执行成功

- [ ] **Step 7: 验证 downgrade 再 upgrade**

```bash
cd backend
uv run alembic downgrade -1
uv run alembic upgrade head
```

Expected: 两次操作都成功

- [ ] **Step 8: 运行测试**

```bash
cd backend
uv run pytest tests/ --ignore=tests/test_agent_debug_flow.py -x -v
```

Expected: 通过

- [ ] **Step 9: 提交**

```bash
git add backend/alembic/versions/ backend/app/models/agent.py backend/app/models/enums.py backend/app/models/__init__.py
git commit -m "chore(db): DROP agent_pending_states 表并清理相关 model 和枚举"
```

---

### Task 4: 修复测试 mock 适配新架构

**Files:**
- Modify: `backend/tests/conftest.py:158-361`
- Modify: `backend/tests/test_agent_debug_flow.py`
- Modify: `backend/tests/test_agent_debug_route.py`
- Modify: `backend/tests/test_web_agent_message_route.py`
- Modify: `backend/tests/test_wechat_inbound.py`
- Modify: `backend/tests/test_wechat_channel_adapter.py`

- [ ] **Step 1: 修复 conftest.py — 删除 FakeLLMClient，修复 graph fixture**

删除 `backend/tests/conftest.py` 第 153-355 行（从 `# FakeLLMClient for Agent tests` 到 `fake_llm_client` fixture 结束）。

将第 358-360 行的 `graph` fixture：
```python
@pytest.fixture()
def graph(db_session: Session, fake_llm_client: FakeLLMClient) -> SchedulePlanningGraph:
    return SchedulePlanningGraph(db_session, llm_client=fake_llm_client)
```

改为：
```python
@pytest.fixture()
def graph(db_session: Session) -> SchedulePlanningGraph:
    return SchedulePlanningGraph(db_session)
```

- [ ] **Step 2: 修复 test_agent_debug_route.py — 更新 FakeGraph 返回值**

将第 22-28 行的 `graph_trace`：
```python
            graph_trace=[
                "load_context",
                "check_pending_state",
                "classify_intent",
                "extract_info",
                "generate_response",
            ],
```

改为：
```python
            graph_trace=["agent_loop"],
```

删除第 21 行 `pending_state=None,`。

将第 46-52 行的断言：
```python
    assert body["data"]["graph_trace"] == [
        "load_context",
        "check_pending_state",
        "classify_intent",
        "extract_info",
        "generate_response",
    ]
```

改为：
```python
    assert body["data"]["graph_trace"] == ["agent_loop"]
```

- [ ] **Step 3: 修复 test_web_agent_message_route.py — 同样更新 FakeGraph**

与 Step 2 相同的修改：删除 `pending_state=None`，更新 `graph_trace` 为 `["agent_loop"]`，更新断言。

- [ ] **Step 4: 修复 test_wechat_inbound.py — 更新 FakeGraph**

将第 57-63 行的 `graph_trace` 更新为 `["agent_loop"]`，删除第 56 行 `pending_state=None,`。

- [ ] **Step 5: 修复 test_wechat_channel_adapter.py — 更新 FakeGraph**

将第 54 行的 `graph_trace` 更新为 `["agent_loop"]`，删除第 53 行 `pending_state=None,`。

- [ ] **Step 6: 修复 test_agent_debug_flow.py — 适配新架构**

这个文件改动最大，需要重构测试逻辑。核心变化：

1. 删除旧导入（第 5-11 行）：
```python
from app.models import (
    AgentPendingState,
    PendingStateStatus,
    ReminderJob,
    ScheduledItem,
    TaskItem,
)
```
改为：
```python
from app.models import ReminderJob, ScheduledItem, TaskItem
```

2. 因为 `graph` fixture 不再接受 `llm_client`，测试需要通过 monkeypatch 模拟 LLM 响应。在每个测试中 monkeypatch `_create_agent_node` 返回的 model：

```python
def _mock_model_response(message_content, tool_calls=None):
    """创建模拟的 LLM 响应。"""
    from langchain_core.messages import AIMessage
    return AIMessage(content=message_content, tool_calls=tool_calls or [])
```

3. 重构 `test_create_event_and_reminder`：
- 删除 `state.graph_trace[:4]` 断言（第 42-47 行）
- 删除 `state.intent == "create_scheduled_item"` 断言（第 40 行）
- 改为断言 `state.final_response` 包含预期内容
- 删除 `state.success is True` 断言，改为 `state.get("success") is True`

4. 重构 `test_query_events_for_tomorrow`：
- 删除 `state.intent == "query_scheduled_items"` 断言
- 改为断言 `final_response` 包含查询结果

5. 重构 `test_plan_task_and_confirm`：
- 删除 `state.pending_state is not None` 断言（第 94 行）
- 删除 `pending = db_session.scalar(select(AgentPendingState)...)` 查询（第 77-82 行）
- 删除 `assert pending is not None` 断言
- 删除 `confirm_state.intent == "confirm_plan"` 断言
- 改为断言 `final_response` 包含预期内容

6. 重构 `test_confirm_plan_replaces_existing_confirmed_plan`：
- 删除 `first_state.pending_state is not None` 断言（第 123 行）
- 删除 `second_state.pending_state is not None` 断言（第 135 行）
- 删除 `confirm_state.success is True` 断言，改为检查 `final_response`

7. 重构 `test_update_and_delete_event`：
- 删除 `update_state.intent == "update_scheduled_item"` 断言（第 170 行）
- 删除 `delete_state.intent == "delete_scheduled_item"` 断言（第 189 行）
- 改为断言 `final_response` 包含预期内容

8. 重构 `test_conflict_clarification_and_cancel`：
- 删除 `conflict_state.pending_state is not None` 断言（第 209 行）
- 删除 `shift_state.pending_state is None` 断言（第 230 行）
- 删除 `clarification_state.pending_state is None` 断言（第 244 行）
- 删除 `cancel_state.pending_state is None` 断言（第 252 行）
- 保留对 `final_response` 内容的断言

- [ ] **Step 7: 运行全部测试**

```bash
cd backend
uv run pytest tests/ -x -v
```

Expected: 全部通过

- [ ] **Step 8: 运行 lint**

```bash
cd backend
uv run ruff check .
```

Expected: 无错误

- [ ] **Step 9: 提交**

```bash
git add backend/tests/
git commit -m "test(agent): 修复测试 mock 适配 LangGraph ReAct 架构"
```

---

### Task 5: 最终验证

- [ ] **Step 1: 运行完整测试套件**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: 全部通过

- [ ] **Step 2: 运行 lint + type check**

```bash
cd backend
uv run ruff check .
uv run mypy app
```

Expected: 无错误

- [ ] **Step 3: 前端构建**

```bash
cd web
pnpm build
```

Expected: 构建成功

- [ ] **Step 4: 手动验证 Debug API**

启动后端，发送测试请求：
```bash
curl -X POST http://localhost:8000/api/agent/debug/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message": "明天下午 3 点开会"}'
```

Expected: 返回成功，`graph_trace` 为 `["agent_loop"]`，无 `pending_state` 字段。
