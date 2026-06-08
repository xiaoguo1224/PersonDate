# Agent 工具调用架构重构设计

## 背景

当前 Agent 采用"意图分类 → 信息抽取 → 路由 → 处理器调工具"的 5 步流程，存在以下问题：

1. **新增工具成本高**：每加一个工具需要改 4 处（IntentDecision 意图、路由、处理器方法、prompt）
2. **工具未充分利用**：21 个已注册工具中，只有 9 个被 Agent 实际调用
3. **prompt 膨胀**：意图分类 prompt 硬编码了工具名和问法映射，维护困难

## 设计目标

1. 新增工具只需在 ToolRegistry 注册 + 加一行描述，不改 prompt
2. LLM 自动发现和调用所有已注册工具
3. 保持 pending_state 多轮对话机制不变
4. 向后兼容，渐进式迁移

## 架构设计

### 核心变化

**现在（5步）：**
```
pending_state检查 → 意图分类(LLM) → 信息抽取(LLM) → 路由(代码) → 调工具(代码) → 生成回复(LLM)
```

**改造后（3步）：**
```
pending_state检查(代码) → LLM选工具+执行(循环) → 返回最终回复
```

### invoke 主流程

```python
def invoke(self, *, current_user, message, conversation_id, channel):
    state = AgentState(...)

    # 1. pending_state 检查（保持不变）
    self._check_pending_state(state)
    if state.pending_state:
        self._handle_pending(state)
        return state

    # 2. 构建 messages
    messages = [
        {"role": "system", "content": self._build_system_prompt(state)},
        {"role": "user", "content": message},
    ]

    # 3. 多轮 tool_calls 循环
    tools = self._build_tools()
    state.final_response = self._run_agent_loop(state, messages, tools)

    state.success = True
    return state
```

### LLMClient 改造

新增 `chat_with_tools` 方法：

```python
def chat_with_tools(
    self,
    *,
    messages: list[dict],
    tools: list[dict],
) -> ChatCompletionMessage:
    response = self.client.chat.completions.create(
        model=self.model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    return response.choices[0].message
```

保留现有 `chat_json` 方法不删除，供其他模块使用。

### 工具定义自动生成

从 ToolRegistry 自动生成 OpenAI tools 格式：

```python
_TOOL_DESCRIPTIONS = {
    "create_scheduled_item": "创建日程安排",
    "query_scheduled_items": "查询日程安排",
    "update_scheduled_item": "修改日程安排",
    "delete_scheduled_item": "删除日程安排",
    "create_task": "创建任务",
    "query_tasks": "查询任务列表",
    "update_task": "修改任务",
    "complete_task": "完成任务",
    "delete_task": "删除任务",
    "analyze_day": "分析某天的安排和任务",
    "find_free_slots": "查找空闲时间段",
    "plan_tasks_into_day": "将任务排入某天生成安排草案",
    "confirm_plan": "确认安排草案",
    "regenerate_plan": "重新生成安排草案",
    "detect_conflicts": "检测日程冲突",
    "suggest_reschedule": "根据冲突建议调整时间",
    "create_reminder": "创建提醒",
    "update_reminder": "修改提醒",
    "cancel_reminder": "取消提醒",
    "query_reminders": "查询提醒列表",
    "ask_user_clarification": "向用户追问信息",
}

def _build_tools(self) -> list[dict]:
    tools = []
    for name in self.tools.registry.names:
        spec = self.tools.registry.get(name)
        schema = spec.schema.model_json_schema()
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": _TOOL_DESCRIPTIONS.get(name, name),
                "parameters": schema,
            }
        })
    return tools
```

新增工具只需：
1. 在 `registry.py` 注册 ToolSpec
2. 在 `_TOOL_DESCRIPTIONS` 加一行描述

### 多轮 tool_calls 循环

```python
def _run_agent_loop(
    self, state: AgentState, messages: list[dict], tools: list[dict]
) -> str:
    for _ in range(5):
        response = self.llm.chat_with_tools(messages=messages, tools=tools)

        if not response.tool_calls:
            return response.content or ""

        # 记录 assistant 消息（含 tool_calls）
        messages.append(response)

        # 执行每个 tool_call
        for tool_call in response.tool_calls:
            result = self._execute_single_tool(state, tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return "处理轮数超限，请简化请求。"
```

### 工具执行

```python
def _execute_single_tool(
    self, state: AgentState, tool_call
) -> dict:
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    result = self.tools.execute(
        name, args,
        user_id=state.user_id,
        conversation_id=state.conversation_id,
    )

    state.tool_calls.append({"tool_name": name, "args": args})
    state.tool_results.append({
        "tool_name": name,
        "result": result.model_dump(mode="json"),
    })

    # 特殊处理：创建日程后检测冲突
    if name == "create_scheduled_item" and result.success:
        self._post_create_check_conflicts(state, result)

    return result.model_dump(mode="json")
```

### System Prompt

```python
def _build_system_prompt(self, state: AgentState) -> str:
    return (
        "你是微信智能日程规划 Agent。"
        "用户通过微信与你对话，管理日程、任务和提醒。"
        "\n\n"
        f"当前时间：{state.current_time.isoformat()}"
        f"用户时区：{state.timezone}"
        "\n\n"
        "规则：\n"
        "1. 单条明确日程可以直接创建\n"
        "2. 复杂规划先用 analyze_day 了解现状，再生成草案\n"
        "3. 存在冲突时询问用户\n"
        "4. 信息不足时追问\n"
        "5. 回复简洁，使用中文\n"
        "6. 不要编造信息，用工具查询实际数据"
    )
```

### pending_state 处理（保持不变）

`_handle_pending()` 方法保持现有逻辑，处理：
- `WAITING_PLAN_CONFIRMATION` - 确认/取消安排草案
- `WAITING_CONFLICT_RESOLUTION` - 冲突选择（1/2/3）
- `WAITING_EVENT_SELECTION` - 事件选择（1/2/3）
- `WAITING_REMINDER_TIME` - 补充提醒时间

## 移除的代码

| 移除项 | 原因 |
|--------|------|
| `IntentDecision` schema | 不再需要意图分类 |
| `MessageExtraction` schema | 不再需要信息抽取 |
| `_classify_intent()` 方法 | LLM 直接选工具 |
| `_extract_info()` 方法 | LLM 直接输出参数 |
| `_classify_and_route()` 方法 | 不再需要路由 |
| `_handle_query_scheduled_items()` | LLM 直接调工具 |
| `_handle_query_free_slots()` | LLM 直接调工具 |
| `_handle_query_reminders()` | LLM 直接调工具 |
| `_handle_create_task()` | LLM 直接调工具 |
| `_handle_plan_day()` | LLM 直接调工具 |
| `_handle_create_scheduled_item()` | LLM 直接调工具 |
| `_handle_update_scheduled_item()` | LLM 直接调工具 |
| `_handle_delete_scheduled_item()` | LLM 直接调工具 |

保留的代码：
- `_check_pending_state()` + `_handle_pending()` - 多轮对话状态机
- `_post_create_check_conflicts()` - 创建后检测冲突
- `_save_log()` - 日志记录
- `_candidate_line()` + `_format_clock_time()` - 辅助函数
- 所有 Tool 实现（registry.py）

## 迁移策略

1. **新增** `chat_with_tools` 方法到 LLMClient
2. **新增** `_build_tools`、`_run_agent_loop`、`_execute_single_tool` 方法
3. **新增** `_build_system_prompt` 方法
4. **修改** `invoke` 调用新流程
5. **测试验证** 用现有测试用例
6. **清理** 移除旧代码

## 预期效果

| 指标 | 现在 | 改造后 |
|------|------|--------|
| 新增工具改动处 | 4处 | 2处（注册+描述） |
| 未接入工具数 | 12个 | 0个 |
| LLM 调用次数 | 2-3次 | 1-N次（多轮） |
| prompt 维护 | 高（硬编码） | 低（自动生成） |
