# LangGraph ReAct Agent 重构设计

## 背景

当前 Agent 使用 Tool-calling Loop 架构（OpenAI 原生 function calling），存在以下问题：

1. 不是标准化框架，维护成本高
2. pending_state 机制手动管理，逻辑复杂
3. 缺少推理过程可观测性

本次重构改为 LangChain + LangGraph 组合：
- LangChain：`@tool` 装饰器定义工具，`ChatOpenAI` + `bind_tools` 调用 LLM
- LangGraph：`StateGraph` 编排 Agent 流程，`interrupt` 实现人机交互

## 设计目标

1. 用 LangChain `@tool` 定义工具，自动生成描述和参数 schema
2. 用 LangGraph `StateGraph` 构建 ReAct Agent
3. 用 LangGraph `interrupt` 替代手动 pending_state 管理
4. 保持向后兼容，渐进式迁移

## 架构设计

### 核心组件

```
backend/app/agent/
  graph.py          # LangGraph StateGraph 定义
  tools.py          # LangChain @tool 工具定义
  state.py          # AgentState 定义
  llm_client.py     # 可能移除，用 LangChain ChatOpenAI 替代
```

### 工具定义（LangChain @tool）

```python
from langchain_core.tools import tool

@tool
def create_scheduled_item(
    title: str,
    start_time: str,
    end_time: str | None = None,
    location: str | None = None,
    remind_before_minutes: int = 0,
) -> dict:
    """创建日程安排。
    
    Args:
        title: 日程标题
        start_time: 开始时间，ISO 8601 格式
        end_time: 结束时间，可选，默认开始后1小时
        location: 地点，可选
        remind_before_minutes: 提前提醒分钟数
    """
    # ... 业务逻辑
```

新增工具只需写一个带 docstring 的函数 + `@tool` 装饰器。

### LangGraph StateGraph

```python
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    conversation_id: str
    timezone: str

tools = [create_scheduled_item, query_scheduled_items, ...]
tool_node = ToolNode(tools)
model = ChatOpenAI(model="gpt-4o-mini").bind_tools(tools)

def agent_node(state: AgentState):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "agent")
app = graph.compile()
```

### interrupt 替代 pending_state

用 LangGraph 的 `interrupt` 实现多轮对话：

```python
from langgraph.types import interrupt

def agent_node(state: AgentState):
    response = model.invoke(state["messages"])
    
    if needs_confirmation(response):
        return interrupt({
            "message": "检测到冲突，请选择处理方式",
            "options": ["保留并忽略", "顺延1小时", "删除"],
        })
    
    return {"messages": [response]}

# 调用时
result = app.invoke({"messages": [("user", "明天下午3点开会")]})
# 如果 interrupt，result 包含中断信息

# 用户回复后继续
result = app.invoke(Command(resume="1"), config=config)
```

pending_state 不再需要手动管理，LangGraph 自动处理状态持久化。

### invoke 入口

```python
class SchedulePlanningGraph:
    def __init__(self, db: Session):
        self.db = db
        self.app = self._build_graph()
    
    def invoke(self, *, current_user, message, conversation_id, channel):
        config = {"configurable": {"thread_id": conversation_id}}
        
        # 检查是否有中断的图需要恢复
        state = self.app.get_state(config)
        if state.next:
            result = self.app.invoke(Command(resume=message), config=config)
        else:
            result = self.app.invoke({
                "messages": [("user", message)],
                "user_id": current_user.id,
                "conversation_id": conversation_id,
                "timezone": current_user.settings.default_timezone,
            }, config=config)
        
        last_message = result["messages"][-1]
        return AgentState(final_response=last_message.content, ...)
```

## 迁移策略

1. 新增 `backend/app/agent/tools.py` - LangChain @tool 工具定义
2. 重写 `backend/app/agent/graph.py` - LangGraph StateGraph
3. 更新 `backend/pyproject.toml` - 新增依赖
4. 测试验证
5. 清理旧代码（LLMClient、IntentDecision、MessageExtraction 等）

## 预期效果

| 指标 | 现在 | 改造后 |
|------|------|--------|
| 工具定义 | registry + schema + 描述字典 | @tool 装饰器 |
| 新增工具改动处 | 2处 | 1处 |
| 状态管理 | 手动 pending_state | LangGraph interrupt |
| 推理可观测性 | 无 | LangGraph Studio |
| 框架标准化 | 自研 | LangChain + LangGraph |
