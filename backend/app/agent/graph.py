from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.agent.llm_client import LLMClient
from app.agent.state import AgentState
from app.core.config import get_settings
from app.models import ConflictStatus, PendingStateType, User
from app.services.agent_log_service import AgentLogService
from app.services.conflict_service import ConflictService
from app.services.pending_state_service import PendingStateService
from app.tools.executor import ToolExecutor

_TOOL_DESCRIPTIONS = {
    "create_scheduled_item": "创建日程安排，需要 title、start_time，可选 end_time、location、remind_before_minutes",
    "query_scheduled_items": "查询日程安排，按日期范围或关键词查询",
    "update_scheduled_item": "修改日程安排，需要 item_id 和要修改的字段",
    "delete_scheduled_item": "删除日程安排，需要 item_id",
    "create_task": "创建任务，需要 title 和 estimated_minutes",
    "query_tasks": "查询任务列表",
    "update_task": "修改任务，需要 task_id 和要修改的字段",
    "complete_task": "完成任务，需要 task_id",
    "delete_task": "删除任务，需要 task_id",
    "analyze_day": "分析某天的安排和任务",
    "find_free_slots": "查找某天的空闲时间段",
    "plan_tasks_into_day": "将未排期任务排入某天生成安排草案",
    "confirm_plan": "确认安排草案，将草案状态改为 active",
    "regenerate_plan": "重新生成安排草案",
    "detect_conflicts": "检测日程冲突",
    "suggest_reschedule": "根据冲突建议调整时间，需要 conflict_id",
    "create_reminder": "创建提醒",
    "update_reminder": "修改提醒",
    "cancel_reminder": "取消提醒",
    "query_reminders": "查询提醒列表",
    "ask_user_clarification": "当信息不足时向用户追问",
}


def _candidate_line(candidate: dict[str, object], index: int, user_tz: ZoneInfo | None = None) -> str:
    raw = candidate["start_time"]
    if isinstance(raw, datetime) and user_tz is not None:
        start = raw.astimezone(user_tz).strftime("%Y-%m-%d %H:%M")
    elif isinstance(raw, datetime):
        start = raw.strftime("%Y-%m-%d %H:%M")
    else:
        start = str(raw).replace("T", " ")[:16]
    return f"{index}. {candidate['title']} {start}"


def _format_clock_time(dt: datetime) -> str:
    hour = dt.hour
    minute = dt.minute
    if hour < 6:
        prefix = "凌晨"
    elif hour < 12:
        prefix = "上午"
    elif hour < 18:
        prefix = "下午"
    else:
        prefix = "晚上"
    display_hour = hour if hour <= 12 else hour - 12
    if minute == 0:
        return f"{prefix} {display_hour} 点"
    return f"{prefix} {display_hour}:{minute:02d}"


class SchedulePlanningGraph:
    def __init__(self, db: Session, llm_client: LLMClient | None = None) -> None:
        self.db = db
        self.tools = ToolExecutor(db)
        self.pending_states = PendingStateService(db)
        self.conflicts = ConflictService(db)
        self.logs = AgentLogService(db)
        self.settings = get_settings()
        self.llm = llm_client or LLMClient()

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
                },
            })
        return tools

    def _build_system_prompt(self, state: AgentState) -> str:
        return (
            "你是微信智能日程规划 Agent。"
            "用户通过微信与你对话，管理日程、任务和提醒。"
            "\n\n"
            f"当前时间：{state.current_time.isoformat()}\n"
            f"用户时区：{state.timezone}\n"
            "\n"
            "规则：\n"
            "1. 单条明确日程可以直接创建\n"
            "2. 复杂规划先用 analyze_day 了解现状，再生成草案\n"
            "3. 存在冲突时询问用户\n"
            "4. 信息不足时追问\n"
            "5. 回复简洁，使用中文\n"
            "6. 不要编造信息，用工具查询实际数据"
        )

    def _execute_single_tool(self, state: AgentState, tool_call) -> dict:
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
        if name == "create_scheduled_item" and result.success:
            self._post_create_check_conflicts(state, result)
        return result.model_dump(mode="json")

    def _run_agent_loop(
        self, state: AgentState, messages: list[dict], tools: list[dict]
    ) -> str:
        for _ in range(5):
            response = self.llm.chat_with_tools(messages=messages, tools=tools)
            if not response.tool_calls:
                return response.content or ""
            messages.append(response.model_dump())
            for tool_call in response.tool_calls:
                result = self._execute_single_tool(state, tool_call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })
        return "处理轮数超限，请简化请求。"

    def invoke(
        self,
        *,
        current_user: User,
        message: str,
        conversation_id: str = "debug",
        channel: str = "wechat",
    ) -> AgentState:
        tz_name = (
            current_user.settings.default_timezone
            if current_user.settings
            else self.settings.default_timezone
        )
        now_local = datetime.now(UTC).astimezone(ZoneInfo(tz_name))
        state = AgentState(
            user_id=current_user.id,
            conversation_id=conversation_id,
            channel=channel,
            input_text=message,
            current_time=now_local,
            timezone=tz_name,
            user_settings={
                "default_timezone": tz_name,
                "default_remind_before_minutes": (
                    current_user.settings.default_remind_before_minutes
                    if current_user.settings
                    else 0
                ),
            },
        )
        graph_trace: list[str] = []
        try:
            graph_trace.append("load_context")
            self._check_pending_state(state)
            graph_trace.append("check_pending_state")
            if state.pending_state:
                self._handle_pending(state)
            else:
                graph_trace.append("agent_loop")
                messages = [
                    {"role": "system", "content": self._build_system_prompt(state)},
                    {"role": "user", "content": message},
                ]
                tools = self._build_tools()
                state.final_response = self._run_agent_loop(state, messages, tools)
            graph_trace.append("generate_response")
            state.success = True
        except Exception as exc:  # noqa: BLE001
            state.success = False
            state.error = str(exc)
            if not state.final_response:
                state.final_response = "处理失败，请稍后再试。"
        finally:
            state.graph_trace = graph_trace
            self._save_log(state, graph_trace)
        return state

    def _save_log(self, state: AgentState, graph_trace: list[str]) -> None:
        self.logs.create_log(
            user_id=state.user_id,
            channel=state.channel,
            conversation_id=state.conversation_id,
            input_text=state.input_text,
            intent=state.intent,
            graph_trace=graph_trace,
            tools_called=state.tool_calls,
            tool_args=[entry.get("args") for entry in state.tool_calls],
            tool_results=state.tool_results,
            final_response=state.final_response,
            success=state.success,
            error_message=state.error,
        )

    def _check_pending_state(self, state: AgentState) -> None:
        pending = self.pending_states.get_active(state.user_id, state.conversation_id)
        if pending is not None:
            state.pending_state = {
                "id": pending.id,
                "state_type": pending.state_type,
                "state_payload": pending.state_payload,
                "expires_at": pending.expires_at,
                "status": pending.status,
            }

    def _post_create_check_conflicts(self, state: AgentState, result) -> None:
        result_data: dict = result.data or {}
        event_id = str(result_data.get("id", ""))
        if not event_id:
            return
        open_conflicts = [
            conflict
            for conflict in self.conflicts.list_conflicts(state.user_id, ConflictStatus.OPEN.value)[0]
            if isinstance(conflict.related_item_ids, dict)
            and (
                conflict.related_item_ids.get("current") == event_id
                or conflict.related_item_ids.get("other") == event_id
            )
        ]
        if open_conflicts:
            title = result_data.get("title", "安排")
            start_raw = result_data.get("start_time")
            end_raw = result_data.get("end_time")
            start_time = datetime.fromisoformat(start_raw) if isinstance(start_raw, str) else start_raw
            end_time = datetime.fromisoformat(end_raw) if isinstance(end_raw, str) else end_raw
            remind_before = result_data.get("remind_before_minutes", 0)
            pending = self.pending_states.save(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                state_type=PendingStateType.WAITING_CONFLICT_RESOLUTION.value,
                state_payload={
                    "event_id": event_id,
                    "event_title": title,
                    "event_start_time": start_time.isoformat() if start_time else None,
                    "event_end_time": end_time.isoformat() if end_time else None,
                    "event_timezone": state.timezone,
                    "remind_before_minutes": remind_before,
                    "conflict_ids": [item.id for item in open_conflicts],
                },
            )
            state.pending_state = pending.state_payload | {
                "id": pending.id,
                "state_type": pending.state_type,
                "status": pending.status,
            }

    def _handle_pending(self, state: AgentState) -> None:
        pending = state.pending_state or {}
        state_type = pending.get("state_type")
        text = state.input_text.strip()
        if text in {"取消", "取消一下"}:
            self.pending_states.clear(state.user_id, state.conversation_id)
            state.final_response = "已取消当前待处理事项。"
            state.pending_state = None
            state.intent = "cancel"
            return
        if (
            text in {"确认", "确认一下"}
            and state_type == PendingStateType.WAITING_PLAN_CONFIRMATION.value
        ):
            self._confirm_plan_from_pending(state)
            return
        if (
            state_type == PendingStateType.WAITING_CONFLICT_RESOLUTION.value
            and text in {"1", "2", "3"}
        ):
            choice = int(text)
            self._handle_conflict_choice(state, choice)
            return
        if state_type == PendingStateType.WAITING_EVENT_SELECTION.value and text in {"1", "2", "3"}:
            choice = int(text)
            self._handle_event_selection_choice(state, choice)
            return
        if state_type == PendingStateType.WAITING_REMINDER_TIME.value and text:
            self._handle_reminder_time_reply(state)
            return
        if state_type == PendingStateType.WAITING_PLAN_CONFIRMATION.value:
            state.final_response = '请回复"确认"继续，或回复"取消"放弃这份安排草案。'
            return
        if state_type == PendingStateType.WAITING_CONFLICT_RESOLUTION.value:
            state.final_response = '请回复 1、2 或 3 处理冲突，或回复"取消"放弃当前处理。'
            return
        if state_type == PendingStateType.WAITING_EVENT_SELECTION.value:
            state.final_response = '请回复候选编号 1、2 或 3，或回复"取消"结束当前操作。'
            return
        if state_type == PendingStateType.WAITING_REMINDER_TIME.value:
            state.final_response = '请告诉我具体提醒时间，例如"明天下午 3 点提醒我"。'
            return
        state.final_response = '我正在等待你的确认或选择，请回复"确认""取消"或序号。'

    def _find_scheduled_item_candidates(
        self,
        state: AgentState,
        *,
        keyword: str | None,
        target_date: date | None,
        target_time: datetime | None,
    ) -> list[dict[str, object]]:
        if keyword and keyword != "安排":
            result = self.tools.execute(
                "query_scheduled_items",
                {"keyword": keyword, "on_date": target_date},
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
            state.tool_calls.append(
                {"tool_name": "query_scheduled_items", "args": {"keyword": keyword, "on_date": target_date}}
            )
            state.tool_results.append(
                {"tool_name": "query_scheduled_items", "result": result.model_dump(mode="json")}
            )
            return result.data or []

        result = self.tools.execute(
            "query_scheduled_items",
            {"start_date": target_date, "end_date": target_date},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {"tool_name": "query_scheduled_items", "args": {"start_date": target_date, "end_date": target_date}}
        )
        state.tool_results.append(
            {"tool_name": "query_scheduled_items", "result": result.model_dump(mode="json")}
        )
        candidates = result.data or []
        if target_time is None:
            return candidates

        target_clock = (target_time.hour, target_time.minute)
        matched: list[dict[str, object]] = []
        for event in candidates:
            start = event.get("start_time")
            if isinstance(start, str):
                try:
                    start_dt = datetime.fromisoformat(start)
                except ValueError:
                    continue
            elif isinstance(start, datetime):
                start_dt = start
            else:
                continue
            if (start_dt.hour, start_dt.minute) == target_clock:
                matched.append(event)
        return matched or candidates

    def _confirm_plan_from_pending(self, state: AgentState) -> None:
        payload = state.pending_state or {}
        state_payload = payload.get("state_payload", {}) if "state_payload" in payload else payload
        plan_date_str = state_payload.get("date")
        if not plan_date_str:
            state.final_response = "没有可确认的安排草案。"
            return
        plan_date = date.fromisoformat(plan_date_str)
        result = self.tools.execute(
            "confirm_plan",
            {"plan_date": plan_date},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append({"tool_name": "confirm_plan", "args": {"plan_date": plan_date}})
        state.tool_results.append(
            {"tool_name": "confirm_plan", "result": result.model_dump(mode="json")}
        )
        if result.success:
            self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
            state.pending_state = None
            state.intent = "confirm_plan"
            state.final_response = "计划已确认。"
            return
        state.final_response = result.error or "确认计划失败。"

    def _handle_conflict_choice(self, state: AgentState, choice: int) -> None:
        payload = state.pending_state or {}
        state_payload = payload.get("state_payload", {}) if "state_payload" in payload else payload
        event_id = state_payload.get("event_id")
        event_title = state_payload.get("event_title") or "安排"
        start_raw = state_payload.get("event_start_time")
        end_raw = state_payload.get("event_end_time")
        timezone = state_payload.get("event_timezone") or state.timezone
        remind_before_minutes = state_payload.get("remind_before_minutes")
        original_start = (
            datetime.fromisoformat(start_raw) if isinstance(start_raw, str)
            else start_raw if isinstance(start_raw, datetime) else None
        )
        original_end = (
            datetime.fromisoformat(end_raw) if isinstance(end_raw, str)
            else end_raw if isinstance(end_raw, datetime) else None
        )
        if choice == 1:
            self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
            state.pending_state = None
            state.final_response = "已保留当前安排，并忽略冲突。"
            return
        if choice == 2 and event_id and original_start is not None:
            new_start = original_start + timedelta(hours=1)
            new_end = (
                original_end + timedelta(hours=1) if original_end is not None
                else new_start + timedelta(hours=1)
            )
            result = self.tools.execute(
                "update_scheduled_item",
                {
                    "item_id": event_id, "title": event_title,
                    "start_time": new_start, "end_time": new_end,
                    "timezone": timezone, "remind_before_minutes": remind_before_minutes,
                },
                user_id=state.user_id, conversation_id=state.conversation_id,
            )
            state.tool_calls.append({
                "tool_name": "update_scheduled_item",
                "args": {"item_id": event_id, "start_time": new_start, "end_time": new_end},
            })
            state.tool_results.append(
                {"tool_name": "update_scheduled_item", "result": result.model_dump(mode="json")}
            )
            if result.success:
                self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
                state.pending_state = None
                local_new_start = new_start.astimezone(ZoneInfo(state.timezone))
                state.final_response = (
                    f"已将当前冲突安排顺延到 {local_new_start:%Y-%m-%d} {_format_clock_time(local_new_start)}。"
                )
                return
            state.final_response = result.error or "顺延安排失败。"
            return
        if choice == 2 and event_id:
            self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
            state.pending_state = None
            state.final_response = "已收到顺延请求，但缺少原始时间，暂时无法自动顺延。"
            return
        if choice == 3 and event_id:
            self.tools.execute(
                "delete_scheduled_item", {"item_id": event_id},
                user_id=state.user_id, conversation_id=state.conversation_id,
            )
            self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
            state.pending_state = None
            state.final_response = "已删除当前冲突安排。"
            return
        state.final_response = "请回复 1、2 或 3 处理冲突。"

    def _handle_event_selection_choice(self, state: AgentState, choice: int) -> None:
        payload = state.pending_state or {}
        candidates = (
            payload.get("state_payload", {}).get("candidates", [])
            if "state_payload" in payload
            else payload.get("candidates", [])
        )
        action = (
            payload.get("state_payload", {}).get("action")
            if "state_payload" in payload
            else payload.get("action")
        )
        if not candidates or choice < 1 or choice > len(candidates):
            state.final_response = "请选择有效的候选编号。"
            return
        candidate = candidates[choice - 1]
        if action == "delete_scheduled_item":
            self.tools.execute(
                "delete_scheduled_item", {"item_id": candidate["id"]},
                user_id=state.user_id, conversation_id=state.conversation_id,
            )
            state.final_response = f'已删除安排「{candidate["title"]}」。'
        elif action == "update_scheduled_item":
            state.final_response = f'已选中安排「{candidate["title"]}」，请继续补充修改内容。'
        self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
        state.pending_state = None

    def _handle_reminder_time_reply(self, state: AgentState) -> None:
        state.final_response = "我已经收到提醒时间，后续可继续补充具体提醒方式。"
        self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
        state.pending_state = None
