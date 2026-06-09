from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import Command
from typing_extensions import TypedDict

from app.agent.tools import ALL_TOOLS
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
        "6. 不要编造信息，用工具查询实际数据"
    )


def _inject_user_id(tool_args: dict, user_id: str) -> dict:
    """注入 user_id 到工具参数"""
    if "user_id" in tool_args:
        tool_args["user_id"] = user_id
    return tool_args


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

        return {
            "messages": [response],
            "tool_calls": existing_calls,
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


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph():
    agent_node = _create_agent_node()
    tool_node = _create_tool_node()

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


class SchedulePlanningGraph:
    def __init__(self, db=None):
        self.db = db
        self.app = build_graph()
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

        config = {"configurable": {"thread_id": conversation_id}}

        result = self.app.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "user_id": current_user.id,
                "conversation_id": conversation_id,
                "timezone": tz_name,
                "current_time": now_local.isoformat(),
                "tool_calls": [],
                "tool_results": [],
            },
            config=config,
        )

        last_message = result["messages"][-1]
        final_response = last_message.content if isinstance(last_message, AIMessage) else ""

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
