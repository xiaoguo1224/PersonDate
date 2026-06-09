from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.agent.tools import ALL_TOOLS, set_user_id
from app.core.config import get_settings
from app.models import User
from app.services.agent_log_service import AgentLogService


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: str
    conversation_id: str
    timezone: str
    current_time: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    needs_confirmation: bool
    confirmation_prompt: str


def _build_system_prompt(state: AgentState) -> str:
    return (
        "你是微信智能日程规划 Agent。"
        "用户通过微信与你对话，管理日程、任务和提醒。"
        "\n\n"
        f"当前时间：{state['current_time']}\n"
        f"用户时区：{state['timezone']}\n"
        "\n"
        "规则：\n"
        "1. 单条明确日程可以直接创建\n"
        "2. 复杂规划先用 analyze_day 了解现状，再生成草案\n"
        "3. 存在冲突时询问用户\n"
        "4. 信息不足时追问\n"
        "5. 回复简洁，使用中文\n"
        "6. 不要编造信息，用工具查询实际数据\n"
        "\n"
        "当你需要用户确认或选择时，在回复末尾加上 [NEED_CONFIRM] 标记。"
        "例如：\n"
        "- 检测到冲突时：'检测到冲突，请选择处理方式。[NEED_CONFIRM]'\n"
        "- 有多个候选时：'找到多个安排，请选择。[NEED_CONFIRM]'\n"
        "- 需要确认计划时：'已生成计划，请确认。[NEED_CONFIRM]'"
    )


def _create_agent_node():
    settings = get_settings()
    model = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model or "gpt-4o-mini",
    ).bind_tools(ALL_TOOLS)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=_build_system_prompt(state))] + messages

        response = model.invoke(messages)

        existing_calls = state.get("tool_calls", [])
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                existing_calls.append({"tool_name": tc["name"], "args": tc["args"]})

        content = response.content or ""
        needs_confirmation = "[NEED_CONFIRM]" in content
        clean_content = content.replace("[NEED_CONFIRM]", "").strip()

        if needs_confirmation:
            response.content = clean_content

        return {
            "messages": [response],
            "tool_calls": existing_calls,
            "needs_confirmation": needs_confirmation,
            "confirmation_prompt": clean_content if needs_confirmation else "",
        }

    return agent_node


def _create_tool_node():
    tool_node = ToolNode(ALL_TOOLS)

    def tool_node_with_tracking(state: AgentState) -> dict:
        result = tool_node.invoke(state)
        messages = result.get("messages", [])

        tool_results = []
        for msg in messages:
            if hasattr(msg, "content"):
                try:
                    data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    tool_results.append({
                        "tool_name": msg.name if hasattr(msg, "name") else "unknown",
                        "result": data,
                    })
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "messages": messages,
            "tool_results": tool_results,
        }

    return tool_node_with_tracking


def _create_human_node():
    def human_node(state: AgentState) -> dict:
        prompt = state.get("confirmation_prompt", "请确认")
        user_response = interrupt(prompt)
        return {
            "messages": [HumanMessage(content=user_response)],
            "needs_confirmation": False,
            "confirmation_prompt": "",
        }

    return human_node


def should_continue(state: AgentState) -> str:
    if state.get("needs_confirmation"):
        return "human"

    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(checkpointer=None):
    agent_node = _create_agent_node()
    tool_node = _create_tool_node()
    human_node = _create_human_node()

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("human", human_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        "human": "human",
        END: END,
    })
    graph.add_edge("tools", "agent")
    graph.add_edge("human", "agent")

    if checkpointer is None:
        checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


class SchedulePlanningGraph:
    def __init__(self, db=None):
        self.db = db
        self.checkpointer = MemorySaver()
        self.app = build_graph(self.checkpointer)
        self.logs = AgentLogService(db) if db else None

    def invoke(
        self,
        *,
        current_user: User,
        message: str,
        conversation_id: str = "debug",
        channel: str = "wechat",
    ) -> dict:
        settings = get_settings()
        tz_name = (
            current_user.settings.default_timezone
            if current_user.settings
            else settings.default_timezone
        )
        now_local = datetime.now(UTC).astimezone(ZoneInfo(tz_name))

        set_user_id(current_user.id)

        config = {"configurable": {"thread_id": conversation_id}}

        state_snapshot = self.app.get_state(config)
        is_interrupted = state_snapshot.next and "human" in state_snapshot.next

        if is_interrupted:
            result = self.app.invoke(
                Command(resume=message),
                config=config,
            )
        else:
            result = self.app.invoke(
                {
                    "messages": [HumanMessage(content=message)],
                    "user_id": current_user.id,
                    "conversation_id": conversation_id,
                    "timezone": tz_name,
                    "current_time": now_local.isoformat(),
                    "tool_calls": [],
                    "tool_results": [],
                    "needs_confirmation": False,
                    "confirmation_prompt": "",
                },
                config=config,
            )

        interrupts = []
        if hasattr(result, "__getitem__") and "__interrupt__" in result:
            for intr in result["__interrupt__"]:
                interrupts.append(intr.value if hasattr(intr, "value") else str(intr))

        last_message = result["messages"][-1]
        final_response = last_message.content if isinstance(last_message, AIMessage) else ""

        if interrupts and not final_response:
            final_response = interrupts[0]

        if self.logs:
            self.logs.create_log(
                user_id=current_user.id,
                channel=channel,
                conversation_id=conversation_id,
                input_text=message,
                intent="",
                graph_trace=["agent_loop"],
                tools_called=result.get("tool_calls", []),
                tool_args=[tc.get("args") for tc in result.get("tool_calls", [])],
                tool_results=result.get("tool_results", []),
                final_response=final_response,
                success=True,
            )

        return {
            "success": True,
            "final_response": final_response,
            "intent": "",
            "tool_calls": result.get("tool_calls", []),
            "tool_results": result.get("tool_results", []),
            "pending_state": None,
            "graph_trace": ["agent_loop"],
            "error": None,
        }
