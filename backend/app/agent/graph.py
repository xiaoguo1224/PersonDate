from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.agent.llm_client import LLMClient
from app.agent.schemas import IntentDecision, MessageExtraction
from app.agent.state import AgentState
from app.core.config import get_settings
from app.models import ConflictStatus, PendingStateType, User
from app.services.agent_log_service import AgentLogService
from app.services.conflict_service import ConflictService
from app.services.pending_state_service import PendingStateService
from app.tools.executor import ToolExecutor


def _candidate_line(candidate: dict[str, object], index: int) -> str:
    start = str(candidate["start_time"]).replace("T", " ")[:16]
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

    def _build_analysis_payload(self, state: AgentState) -> str:
        payload = {
            "message": state.input_text,
            "current_time": state.current_time.isoformat(),
            "timezone": state.timezone,
            "user_settings": state.user_settings or {},
            "pending_state": state.pending_state,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _classify_intent(self, state: AgentState) -> IntentDecision:
        return self.llm.chat_json(
            system_prompt=(
                "你是微信智能安排规划 Agent 的意图分类器。"
                "只输出 JSON，不要输出多余文本。"
                "请根据用户输入判断 intent。"
                "可选值：create_scheduled_item, query_scheduled_items, create_task, plan_day, "
                "update_scheduled_item, delete_scheduled_item, confirm_plan, "
                "ask_user_clarification, unknown。"
                "如果用户说“帮我安排一下”“安排一下”“生成计划”“计划一下”，"
                "必须返回 plan_day。"
                "如果消息同时包含任务时长或任务事项，但明确要求安排计划，"
                "也不要返回 create_event。"
                "如果用户明确是在确认或取消待办流程，请优先返回 confirm_plan 或 "
                "ask_user_clarification，具体以上下文为准。"
            ),
            user_prompt=self._build_analysis_payload(state),
            schema=IntentDecision,
        )

    def _extract_info(self, state: AgentState, intent: str) -> MessageExtraction:
        payload = json.loads(self._build_analysis_payload(state))
        payload["intent"] = intent
        return self.llm.chat_json(
            system_prompt=(
                "你是微信智能安排规划 Agent 的结构化信息抽取器。"
                "只输出 JSON，不要输出多余文本。"
                "请把用户输入中的相对时间解析成当前时区下的绝对日期或时间。"
                "所有时间字段请使用 ISO 8601。"
                "如果 intent 是 create_event，优先输出 event_title 和 event_start_time。"
                "如果用户只提供了开始时间，没有提供结束时间，不要追问持续时间，"
                "end_time 可以留空，处理层会默认 1 小时。"
                "如果 intent 是 update_event，请尽量输出 original_time 或 event_start_time，"
                "以及 new_time 或 new_start_time。"
                "如果 intent 是 delete_event，请尽量输出 event_start_time。"
                "如果 intent 是 query_events，请输出 date。"
                "如果 intent 是 plan_day 或 create_task，请输出 task_title、"
                "estimated_minutes、plan_date，或者返回 events 列表。"
                "只有在确实无法继续时，才把 clarification_prompt 写成中文追问。"
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False, default=str),
            schema=MessageExtraction,
        )

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
                graph_trace.append("classify_intent")
                decision = self._classify_intent(state)
                state.intent = decision.intent
                graph_trace.append("extract_info")
                extracted = self._extract_info(state, decision.intent)
                state.extracted = {
                    "intent": decision.intent,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    **extracted.model_dump(),
                }
                self._classify_and_route(state)
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

    def _classify_and_route(self, state: AgentState) -> None:
        text = state.input_text.strip()
        if text in {"取消", "取消一下"}:
            state.intent = "cancel"
            state.final_response = "已取消当前待处理事项。"
            return
        intent = state.intent or "unknown"
        if intent == "ask_user_clarification":
            state.final_response = self._ask_user_clarification(state)
            return
        if intent == "query_scheduled_items":
            self._handle_query_scheduled_items(state)
            return
        if intent == "delete_scheduled_item":
            self._handle_delete_scheduled_item(state)
            return
        if intent == "update_scheduled_item":
            self._handle_update_scheduled_item(state)
            return
        if intent == "create_task":
            self._handle_create_task(state)
            return
        if intent == "plan_day":
            self._handle_plan_day(state)
            return
        if intent == "create_scheduled_item":
            self._handle_create_scheduled_item(state)
            return
        if intent == "confirm_plan":
            state.final_response = "请在待确认的安排草案上下文中回复“确认”或“取消”。"
            return
        state.final_response = "我没能理解这条消息，请补充时间、事项或目标。"

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
            state.final_response = "请回复“确认”继续，或回复“取消”放弃这份安排草案。"
            return
        if state_type == PendingStateType.WAITING_CONFLICT_RESOLUTION.value:
            state.final_response = "请回复 1、2 或 3 处理冲突，或回复“取消”放弃当前处理。"
            return
        if state_type == PendingStateType.WAITING_EVENT_SELECTION.value:
            state.final_response = "请回复候选编号 1、2 或 3，或回复“取消”结束当前操作。"
            return
        if state_type == PendingStateType.WAITING_REMINDER_TIME.value:
            state.final_response = "请告诉我具体提醒时间，例如“明天下午 3 点提醒我”。"
            return
        state.final_response = "我正在等待你的确认或选择，请回复“确认”“取消”或序号。"

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
                {
                    "tool_name": "query_scheduled_items",
                    "args": {"keyword": keyword, "on_date": target_date},
                }
            )
            state.tool_results.append(
                {
                    "tool_name": "query_scheduled_items",
                    "result": result.model_dump(mode="json"),
                }
            )
            return result.data or []

        result = self.tools.execute(
            "query_scheduled_items",
            {"start_date": target_date, "end_date": target_date},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {
                "tool_name": "query_scheduled_items",
                "args": {"start_date": target_date, "end_date": target_date},
            }
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

    def _handle_create_event(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        title = extracted.get("event_title") or "安排"
        start_time = extracted.get("event_start_time")
        end_time = extracted.get("event_end_time")
        remind_before = extracted.get("remind_before_minutes")
        if start_time is None:
            state.intent = "ask_user_clarification"
            state.final_response = (
                extracted.get("clarification_prompt")
                or "请补充具体时间，例如“明天下午 3 点开会”。"
            )
            return
        if end_time is None:
            end_time = start_time + timedelta(hours=1)
        if remind_before is None:
            remind_before = (
                state.user_settings.get("default_remind_before_minutes", 0)
                if state.user_settings
                else 0
            )
        result = self.tools.execute(
            "create_scheduled_item",
            {
                "title": title,
                "description": None,
                "start_time": start_time,
                "end_time": end_time,
                "timezone": state.timezone,
                "location": None,
                "remind_before_minutes": remind_before,
            },
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {
                "tool_name": "create_scheduled_item",
                "args": {"title": title, "start_time": start_time, "end_time": end_time},
            }
        )
        state.tool_results.append(
            {"tool_name": "create_scheduled_item", "result": result.model_dump(mode="json")}
        )
        if not result.success:
            state.final_response = result.error or "创建安排失败。"
            return
        result_data: dict[str, object] = result.data or {}
        event_id = str(result_data["id"])
        open_conflicts = [
            conflict
            for conflict in self.conflicts.list_conflicts(state.user_id, ConflictStatus.OPEN.value)
            if isinstance(conflict.related_item_ids, dict)
            and (
                conflict.related_item_ids.get("current") == event_id
                or conflict.related_item_ids.get("other") == event_id
            )
        ]
        if open_conflicts:
            pending = self.pending_states.save(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                state_type=PendingStateType.WAITING_CONFLICT_RESOLUTION.value,
                state_payload={
                    "event_id": event_id,
                    "event_title": title,
                    "event_start_time": start_time.isoformat(),
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
            lines = [f"已创建安排：{title}，时间为 {start_time.strftime('%Y-%m-%d %H:%M')}。"]
            lines.append("但检测到冲突，请回复 1、2 或 3 选择处理方式。")
            lines.append("1. 保留当前安排并忽略冲突")
            lines.append("2. 将当前安排顺延 1 小时")
            lines.append("3. 删除当前安排")
            state.final_response = "\n".join(lines)
            return
        state.final_response = (
            f"已为你创建安排：{title}，时间为 {start_time.strftime('%Y-%m-%d %H:%M')}。"
        )

    def _handle_query_events(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        target_date = extracted.get("query_start_date") or extracted.get("query_end_date")
        if target_date is None:
            target_date = state.current_time.date()
        result = self.tools.execute(
            "query_scheduled_items",
            {"start_date": target_date, "end_date": target_date},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {
                "tool_name": "query_scheduled_items",
                "args": {"start_date": target_date, "end_date": target_date},
            }
        )
        state.tool_results.append(
            {"tool_name": "query_scheduled_items", "result": result.model_dump(mode="json")}
        )
        events = result.data or []
        state.scheduled_items = events
        if not events:
            state.final_response = f"{target_date.isoformat()} 没有安排。"
            return
        lines = [f"{target_date.isoformat()} 的安排："]
        for index, event in enumerate(events, start=1):
            start = event["start_time"]
            end = event.get("end_time")
            if isinstance(start, str):
                start_text = start.replace("T", " ")[:16]
            else:
                start_text = str(start)
            if isinstance(end, str):
                end_text = end.replace("T", " ")[:16]
            else:
                end_text = str(end)
            lines.append(f"{index}. {event['title']} {start_text} - {end_text}")
        state.final_response = "\n".join(lines)

    def _handle_create_task(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        minutes = extracted.get("estimated_minutes")
        title = extracted.get("task_title") or "任务"
        if minutes is None:
            state.intent = "ask_user_clarification"
            state.final_response = (
                extracted.get("clarification_prompt") or "请补充任务时长，例如“明天写论文 2 小时”。"
            )
            return
        result = self.tools.execute(
            "create_task",
            {
                "title": title,
                "description": None,
                "estimated_minutes": minutes,
                "deadline": None,
                "priority": "medium",
            },
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {"tool_name": "create_task", "args": {"title": title, "estimated_minutes": minutes}}
        )
        state.tool_results.append(
            {"tool_name": "create_task", "result": result.model_dump(mode="json")}
        )
        if state.intent == "plan_day":
            target_date = extracted.get("plan_date") or state.current_time.date()
            plan_result = self.tools.execute(
                "plan_tasks_into_day",
                {"plan_date": target_date},
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
            state.tool_calls.append(
                {"tool_name": "plan_tasks_into_day", "args": {"plan_date": target_date}}
            )
            state.tool_results.append(
                {"tool_name": "plan_tasks_into_day", "result": plan_result.model_dump(mode="json")}
            )
            if plan_result.success:
                pending = self.pending_states.save(
                    user_id=state.user_id,
                    conversation_id=state.conversation_id,
                    state_type=PendingStateType.WAITING_PLAN_CONFIRMATION.value,
                    state_payload={"date": target_date.isoformat()},
                )
                state.pending_state = pending.state_payload | {
                    "id": pending.id,
                    "state_type": pending.state_type,
                    "status": pending.status,
                }
                state.final_response = (
                    f"已创建任务：{title}，预计 {minutes} 分钟。\n"
                    f"已生成 {target_date.isoformat()} 的安排草案，请回复“确认”或“取消”。"
                )
                return
        state.final_response = f"已创建任务：{title}，预计 {minutes} 分钟。"

    def _handle_plan_day(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        target_date = extracted.get("plan_date") or state.current_time.date()
        task_minutes = extracted.get("estimated_minutes")
        task_title = extracted.get("task_title") or "任务"
        if task_minutes is not None:
            create_task_result = self.tools.execute(
                "create_task",
                {
                    "title": task_title,
                    "description": None,
                    "estimated_minutes": task_minutes,
                    "deadline": None,
                    "priority": "medium",
                },
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
            state.tool_calls.append(
                {
                    "tool_name": "create_task",
                    "args": {
                        "title": task_title,
                        "estimated_minutes": task_minutes,
                    },
                }
            )
            state.tool_results.append(
                {"tool_name": "create_task", "result": create_task_result.model_dump(mode="json")}
            )
        result = self.tools.execute(
            "plan_tasks_into_day",
            {"plan_date": target_date},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {"tool_name": "plan_tasks_into_day", "args": {"plan_date": target_date}}
        )
        state.tool_results.append(
            {"tool_name": "plan_tasks_into_day", "result": result.model_dump(mode="json")}
        )
        if not result.success:
            state.final_response = result.error or "生成计划失败。"
            return
        pending = self.pending_states.save(
            user_id=state.user_id,
            conversation_id=state.conversation_id,
            state_type=PendingStateType.WAITING_PLAN_CONFIRMATION.value,
            state_payload={"date": target_date.isoformat()},
        )
        state.pending_state = pending.state_payload | {
            "id": pending.id,
            "state_type": pending.state_type,
            "status": pending.status,
        }
        state.final_response = (
            f"已生成 {target_date.isoformat()} 的安排草案，请回复“确认”或“取消”。"
        )

    def _handle_update_event(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        keyword = extracted.get("target_event_keyword")
        target_time = extracted.get("original_time") or extracted.get("event_start_time")
        target_date = extracted.get("target_event_date")
        if target_date is None and isinstance(target_time, datetime):
            target_date = target_time.date()
        candidates = self._find_event_candidates(
            state,
            keyword=keyword,
            target_date=target_date,
            target_time=target_time if isinstance(target_time, datetime) else None,
        )
        state.candidate_scheduled_items = candidates
        if not candidates:
            state.final_response = "没有找到可修改的安排。"
            return
        if len(candidates) > 1:
            pending = self.pending_states.save(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                state_type=PendingStateType.WAITING_EVENT_SELECTION.value,
                state_payload={
                    "action": "update_scheduled_item",
                    "candidates": candidates[:3],
                },
            )
            state.pending_state = pending.state_payload | {
                "id": pending.id,
                "state_type": pending.state_type,
                "status": pending.status,
            }
            lines = ["找到多个候选安排，请回复序号选择："]
            for index, candidate in enumerate(candidates[:3], start=1):
                lines.append(_candidate_line(candidate, index))
            state.final_response = "\n".join(lines)
            return
        candidate = candidates[0]
        new_start = extracted.get("new_start_time")
        new_end = extracted.get("new_end_time")
        if new_start is None:
            state.final_response = (
                extracted.get("clarification_prompt") or "请补充新的时间，例如“改到 4 点”。"
            )
            return
        if new_end is None:
            new_end = new_start + timedelta(hours=1)
        update_result = self.tools.execute(
            "update_scheduled_item",
            {
                "event_id": candidate["id"],
                "title": candidate["title"],
                "start_time": new_start,
                "end_time": new_end,
                "timezone": state.timezone,
            },
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {
                "tool_name": "update_scheduled_item",
                "args": {"event_id": candidate["id"], "start_time": new_start, "end_time": new_end},
            }
        )
        state.tool_results.append(
            {"tool_name": "update_scheduled_item", "result": update_result.model_dump(mode="json")}
        )
        if not update_result.success:
            state.final_response = update_result.error or "修改安排失败。"
            return
        state.final_response = (
            f"已将安排“{candidate['title']}”调整到 {new_start:%Y-%m-%d} "
            f"{_format_clock_time(new_start)}。"
        )

    def _handle_delete_event(self, state: AgentState) -> None:
        extracted = state.extracted or {}
        keyword = extracted.get("target_event_keyword")
        target_time = extracted.get("event_start_time") or extracted.get("original_time")
        target_date = extracted.get("target_event_date")
        if target_date is None and isinstance(target_time, datetime):
            target_date = target_time.date()
        candidates = self._find_event_candidates(
            state,
            keyword=keyword,
            target_date=target_date,
            target_time=target_time if isinstance(target_time, datetime) else None,
        )
        state.candidate_scheduled_items = candidates
        if not candidates:
            state.final_response = "没有找到可删除的安排。"
            return
        if len(candidates) > 1:
            pending = self.pending_states.save(
                user_id=state.user_id,
                conversation_id=state.conversation_id,
                state_type=PendingStateType.WAITING_EVENT_SELECTION.value,
                state_payload={
                    "action": "delete_scheduled_item",
                    "candidates": candidates[:3],
                },
            )
            state.pending_state = pending.state_payload | {
                "id": pending.id,
                "state_type": pending.state_type,
                "status": pending.status,
            }
            lines = ["找到多个候选安排，请回复序号选择："]
            for index, candidate in enumerate(candidates[:3], start=1):
                lines.append(_candidate_line(candidate, index))
            state.final_response = "\n".join(lines)
            return
        candidate = candidates[0]
        delete_result = self.tools.execute(
            "delete_scheduled_item",
            {"event_id": candidate["id"]},
            user_id=state.user_id,
            conversation_id=state.conversation_id,
        )
        state.tool_calls.append(
            {"tool_name": "delete_scheduled_item", "args": {"event_id": candidate["id"]}}
        )
        state.tool_results.append(
            {"tool_name": "delete_scheduled_item", "result": delete_result.model_dump(mode="json")}
        )
        state.final_response = f"已删除安排“{candidate['title']}”。"

    def _confirm_plan_from_pending(self, state: AgentState) -> None:
        payload = state.pending_state or {}
        state_payload = payload.get("state_payload", {}) if "state_payload" in payload else payload
        plan_date_str = state_payload.get("date")
        if not plan_date_str:
            state.final_response = "没有可确认的安排草案。"
            return
        from datetime import date as date_type
        plan_date = date_type.fromisoformat(plan_date_str)
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
            datetime.fromisoformat(start_raw)
            if isinstance(start_raw, str)
            else start_raw
            if isinstance(start_raw, datetime)
            else None
        )
        original_end = (
            datetime.fromisoformat(end_raw)
            if isinstance(end_raw, str)
            else end_raw
            if isinstance(end_raw, datetime)
            else None
        )
        if choice == 1:
            self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
            state.pending_state = None
            state.final_response = "已保留当前安排，并忽略冲突。"
            return
        if choice == 2 and event_id and original_start is not None:
            new_start = original_start + timedelta(hours=1)
            new_end = (
                original_end + timedelta(hours=1)
                if original_end is not None
                else new_start + timedelta(hours=1)
            )
            result = self.tools.execute(
                "update_scheduled_item",
                {
                    "event_id": event_id,
                    "title": event_title,
                    "start_time": new_start,
                    "end_time": new_end,
                    "timezone": timezone,
                    "remind_before_minutes": remind_before_minutes,
                },
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
            state.tool_calls.append(
                {
                    "tool_name": "update_scheduled_item",
                    "args": {
                        "event_id": event_id,
                        "start_time": new_start,
                        "end_time": new_end,
                    },
                }
            )
            state.tool_results.append(
                {"tool_name": "update_scheduled_item", "result": result.model_dump(mode="json")}
            )
            if result.success:
                self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
                state.pending_state = None
                state.final_response = (
                    f"已将当前冲突安排顺延到 {new_start:%Y-%m-%d} {_format_clock_time(new_start)}。"
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
                "delete_scheduled_item",
                {"event_id": event_id},
                user_id=state.user_id,
                conversation_id=state.conversation_id,
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
                "delete_scheduled_item",
                {"event_id": candidate["id"]},
                user_id=state.user_id,
                conversation_id=state.conversation_id,
            )
            state.final_response = f"已删除安排“{candidate['title']}”。"
        elif action == "update_scheduled_item":
            state.final_response = f"已选中安排“{candidate['title']}”，请继续补充修改内容。"
        self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
        state.pending_state = None

    def _handle_reminder_time_reply(self, state: AgentState) -> None:
        state.final_response = "我已经收到提醒时间，后续可继续补充具体提醒方式。"
        self.pending_states.clear(state.user_id, state.conversation_id, status="completed")
        state.pending_state = None

    def _ask_user_clarification(self, state: AgentState) -> str:
        extracted = state.extracted or {}
        prompt = extracted.get("clarification_prompt")
        return prompt or "请补充更多信息，我才能继续处理。"
