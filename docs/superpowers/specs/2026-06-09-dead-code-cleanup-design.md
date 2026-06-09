# 旧逻辑残留清理设计

## 背景

项目经历了两次重大架构重构：

1. `6e0bce7` OpenAI function calling → LangChain + LangGraph
2. `ea46192` pending_state 手动管理 → LangGraph interrupt

当前新架构已完全跑通（`graph.py` 使用 LangGraph ReAct + `@tool` + `interrupt`），但旧代码大量残留，包括约 1,500 行死代码文件、pending_state 兼容层、5 个过时测试文件。

## 清理策略

采用按依赖层自底向上清理，分 4 次提交，每批独立可验证。

## 提交 1：删除死代码文件

删除以下 10 个文件，共约 1,440 行：

| 文件 | 行数 | 说明 |
|---|---|---|
| `backend/app/tools/__init__.py` | 1 | 空导出 |
| `backend/app/tools/schemas.py` | 148 | 旧 ToolResult / *Args |
| `backend/app/tools/registry.py` | 605 | 旧 ToolSpec / ToolRegistry |
| `backend/app/tools/executor.py` | 38 | 旧 ToolExecutor |
| `backend/app/agent/schemas.py` | 265 | 旧 IntentDecision / MessageExtraction |
| `backend/app/agent/llm_client.py` | 74 | 旧 OpenAI SDK 封装 |
| `backend/app/agent/parsing.py` | 121 | 旧正则解析 |
| `backend/app/agent/state.py` | 32 | 旧 Pydantic AgentState |
| `backend/app/services/pending_state_service.py` | 95 | 旧 PendingStateService |
| `backend/tests/test_llm_client.py` | 62 | 测试已废弃的 LLMClient |

同步修改：
- `backend/app/core/cache_invalidator.py`：删除 `invalidate_pending_state()` 函数（第 51-53 行）

验证：`uv run pytest`（排除后续才修的过时测试）、`uv run ruff check .`

## 提交 2：移除 pending_state 兼容层

后端改动：

| 文件 | 改动 |
|---|---|
| `backend/app/agent/graph.py` | 删除第 21 行 `PendingStateType/PendingStateStatus` 导入；删除第 453-466 行 pending_state 构造逻辑；返回值 `"pending_state"` 固定为 `None` |
| `backend/app/schemas/agent.py` | 删除第 14 行 `pending_state: dict \| None = None` 字段 |
| `backend/app/api/routes/agent.py` | 删除第 35 行 `pending_state=result.get("pending_state")` |

前端改动：

| 文件 | 改动 |
|---|---|
| `web/lib/dashboard.ts` | 删除第 330 行 `pending_state` 类型字段 |
| `web/app/dashboard/today/page.tsx` | 删除第 902 行 `result.pending_state ? "当前处于待处理状态" : null` |

验证：`uv run ruff check .`、`pnpm build`、手动测试 `POST /api/agent/debug/message`

## 提交 3：DROP TABLE + 清理 models

新建 Alembic migration：

```python
def upgrade():
    op.drop_table("agent_pending_states")

def downgrade():
    # 重建表（从 0001_initial_schema.py 复制建表语句）
```

清理 models：

| 文件 | 改动 |
|---|---|
| `backend/app/models/agent.py` | 删除第 37-53 行 `AgentPendingState` 类 |
| `backend/app/models/enums.py` | 删除第 142-155 行 `PendingStateType` 和 `PendingStateStatus` 枚举 |
| `backend/app/models/__init__.py` | 删除 `AgentPendingState`、`PendingStateType`、`PendingStateStatus` 的导入和 `__all__` 导出 |

验证：`uv run alembic upgrade head`、`uv run alembic downgrade -1` 再 `upgrade head`、`uv run pytest`（排除待修测试）

## 提交 4：修复测试 mock 适配新架构

### 4.1 修复 conftest.py

- 删除 `FakeLLMClient` 类（第 158-350 行）及其 `fake_llm_client` fixture
- 修复 `graph` fixture：`SchedulePlanningGraph(db_session)` 不传 `llm_client`

### 4.2 重写 test_agent_debug_flow.py

- 删除 `AgentPendingState`、`PendingStateStatus` 导入
- 删除对 `state.pending_state` 的断言
- trace 步骤断言从 `"check_pending_state"`, `"classify_intent"`, `"extract_info"`, `"generate_response"` 改为 `["agent_loop"]`
- 因为新架构用 LangGraph ReAct，不再有独立的意图分类和信息抽取节点，部分测试用例需要调整断言逻辑（比如不再断言 `intent` 字段的具体值，改为断言 `final_response` 非空或包含关键词）

### 4.3 更新 4 个测试文件的 FakeGraph mock

- `test_agent_debug_route.py`
- `test_web_agent_message_route.py`
- `test_wechat_inbound.py`
- `test_wechat_channel_adapter.py`

统一修改：`FakeGraph.invoke()` 返回值中删除 `pending_state`，`graph_trace` 改为 `["agent_loop"]`

验证：`uv run pytest` 全部通过、`uv run ruff check .`
