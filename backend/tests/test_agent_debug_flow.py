from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select

from app.agent.graph import SchedulePlanningGraph
from app.models import ReminderJob, ScheduledItem, TaskItem
from app.models.enums import ReminderTargetType
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class FakeChatOpenAI:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.tools = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    def invoke(self, messages):
        last_human_index = max(
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        )
        last_human = messages[last_human_index].content
        last_ai_content = ""
        for message in reversed(messages[:last_human_index]):
            if isinstance(message, AIMessage):
                last_ai_content = message.content or ""
                break
        tool_messages = [
            message
            for message in messages[last_human_index + 1 :]
            if isinstance(message, ToolMessage)
        ]
        tool_names = [message.name for message in tool_messages]

        if last_human == "明天下午 3 点开会":
            same_requests = sum(
                1
                for message in messages
                if isinstance(message, HumanMessage) and message.content == last_human
            )
            if same_requests >= 2:
                return AIMessage(
                    content=(
                        "检测到时间冲突，请选择处理方式："
                        "1 保持原样，2 顺延到 4 点。[NEED_CONFIRM]"
                    )
                )
            if not tool_messages:
                return _tool_call(
                    "create_scheduled_item",
                    {
                        "title": "会议",
                        "start_time": _tomorrow_at(15).isoformat(),
                        "end_time": _tomorrow_at(16).isoformat(),
                        "remind_before_minutes": 0,
                        "timezone": "Asia/Shanghai",
                    },
                )
            return AIMessage(content="已为你创建安排：会议。")

        if last_human == "明天有什么安排？":
            if not tool_messages:
                return _tool_call(
                    "query_scheduled_items",
                    {"on_date": _tomorrow_date().isoformat()},
                )
            items = _tool_result(tool_messages[-1]).get("data", [])
            titles = "、".join(item["title"] for item in items) if items else "暂无安排"
            return AIMessage(content=f"明天的安排：{titles}")

        if last_human == "明天写论文 2 小时，帮我安排一下":
            if not tool_messages:
                return _tool_call(
                    "create_task",
                    {
                        "title": "写论文",
                        "estimated_minutes": 120,
                    },
                )
            if tool_names == ["create_task"]:
                return _tool_call(
                    "plan_tasks_into_day",
                    {"plan_date": _tomorrow_date().isoformat()},
                )
            return AIMessage(content="已生成计划，请确认。[NEED_CONFIRM]")

        if last_human == "确认":
            if "删除" in last_ai_content:
                if not tool_messages:
                    return _tool_call(
                        "query_scheduled_items",
                        {"on_date": _tomorrow_date().isoformat()},
                    )
                if tool_names == ["query_scheduled_items"]:
                    item_id = _pick_item_id(tool_messages[-1], local_hour=16)
                    return _tool_call("delete_scheduled_item", {"item_id": item_id})
                return AIMessage(content="安排已删除。")
            if not tool_messages:
                return _tool_call(
                    "confirm_plan",
                    {"plan_date": _tomorrow_date().isoformat()},
                )
            return AIMessage(content="计划已确认。")

        if last_human == "把明天下午 3 点的会议改到 4 点":
            if not tool_messages:
                return _tool_call(
                    "query_scheduled_items",
                    {"on_date": _tomorrow_date().isoformat()},
                )
            if tool_names == ["query_scheduled_items"]:
                item_id = _pick_item_id(tool_messages[-1], local_hour=15)
                return _tool_call(
                    "update_scheduled_item",
                    {
                        "item_id": item_id,
                        "start_time": _tomorrow_at(16).isoformat(),
                        "end_time": _tomorrow_at(17).isoformat(),
                    },
                )
            return AIMessage(content="已改到明天下午 4 点。")

        if last_human == "删除明天下午 4 点的会议":
            return AIMessage(content="确定要删除明天下午 4 点的会议吗？[NEED_CONFIRM]")

        if last_human == "2":
            if not tool_messages:
                return _tool_call(
                    "create_scheduled_item",
                    {
                        "title": "会议",
                        "start_time": _tomorrow_at(16).isoformat(),
                        "end_time": _tomorrow_at(17).isoformat(),
                        "remind_before_minutes": 0,
                        "timezone": "Asia/Shanghai",
                    },
                )
            return AIMessage(content="已顺延到 4 点。")

        if last_human == "提醒我写论文":
            return AIMessage(content="请告诉我具体提醒时间。[NEED_CONFIRM]")

        if last_human == "取消":
            return AIMessage(content="已取消。")

        raise AssertionError(f"未覆盖的测试消息: {last_human}")


class _SessionProxy:
    def __init__(self, session) -> None:
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self) -> None:
        return None


class _GraphWrapper:
    def __init__(self, graph: SchedulePlanningGraph) -> None:
        self._graph = graph

    def invoke(self, **kwargs):
        return SimpleNamespace(**self._graph.invoke(**kwargs))


def _tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": f"call_{name}",
                "name": name,
                "args": args,
                "type": "tool_call",
            }
        ],
    )


def _tool_result(message: ToolMessage) -> dict:
    return json.loads(message.content)


def _tomorrow_date():
    return datetime.now(UTC).astimezone(_SHANGHAI_TZ).date() + timedelta(days=1)


def _tomorrow_at(hour: int) -> datetime:
    return datetime.combine(_tomorrow_date(), time(hour=hour), _SHANGHAI_TZ)


def _local_hour(value: datetime) -> int:
    return value.astimezone(_SHANGHAI_TZ).hour


def _pick_item_id(message: ToolMessage, *, local_hour: int) -> str:
    for item in _tool_result(message).get("data", []):
        if _local_hour(datetime.fromisoformat(item["start_time"])) == local_hour:
            return item["id"]
    raise AssertionError(f"未找到本地时间 {local_hour} 点的安排")


@pytest.fixture()
def graph(monkeypatch, db_session):
    session_proxy = _SessionProxy(db_session)
    monkeypatch.setattr("app.agent.graph.ChatOpenAI", FakeChatOpenAI)
    monkeypatch.setattr("app.agent.tools.SessionLocal", lambda: session_proxy)
    return _GraphWrapper(SchedulePlanningGraph(db_session))


def _create_owner(db_session):
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()
    db_session.refresh(owner)
    return owner


def test_create_event_and_reminder(db_session, graph) -> None:
    owner = _create_owner(db_session)

    state = graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug-create",
    )
    db_session.commit()

    event = db_session.scalar(select(ScheduledItem).where(ScheduledItem.user_id == owner.id))
    reminder = db_session.scalar(select(ReminderJob).where(ReminderJob.user_id == owner.id))

    assert state.success is True
    assert "已为你创建安排" in (state.final_response or "")
    assert event is not None
    assert event.title == "会议"
    assert reminder is not None


def test_query_events_for_tomorrow(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug-query",
    )
    db_session.commit()

    state = graph.invoke(
        current_user=owner,
        message="明天有什么安排？",
        conversation_id="debug-query",
    )
    db_session.commit()

    assert "的安排" in (state.final_response or "")
    assert "会议" in (state.final_response or "")


def test_plan_task_and_confirm(db_session, graph) -> None:
    owner = _create_owner(db_session)

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug-plan",
    )
    db_session.commit()

    task = db_session.scalar(select(TaskItem).where(TaskItem.user_id == owner.id))
    draft_items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
                ScheduledItem.status == "draft",
            )
        )
    )

    assert task is not None
    assert task.title == "写论文"
    assert len(draft_items) >= 1

    draft_reminders = list(
        db_session.scalars(
            select(ReminderJob).where(
                ReminderJob.user_id == owner.id,
                ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
                ReminderJob.status == "pending",
            )
        )
    )
    assert len(draft_reminders) == 0

    for item in draft_items:
        item.remind_before_minutes = 0
    db_session.commit()

    confirm_state = graph.invoke(
        current_user=owner,
        message="确认",
        conversation_id="debug-plan",
    )
    db_session.commit()
    confirmed_items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
                ScheduledItem.status == "active",
            )
        )
    )
    pending_reminders = list(
        db_session.scalars(
            select(ReminderJob).where(
                ReminderJob.user_id == owner.id,
                ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
                ReminderJob.status == "pending",
            )
        )
    )

    assert "计划已确认" in (confirm_state.final_response or "")
    assert len(confirmed_items) >= 1
    assert len(pending_reminders) == len(confirmed_items)


def test_confirm_plan_replaces_existing_confirmed_plan(db_session, graph) -> None:
    owner = _create_owner(db_session)

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug-replan",
    )
    db_session.commit()

    first_confirm = graph.invoke(
        current_user=owner,
        message="确认",
        conversation_id="debug-replan",
    )
    db_session.commit()
    assert first_confirm.success is True

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug-replan",
    )
    db_session.commit()

    second_confirm = graph.invoke(
        current_user=owner,
        message="确认",
        conversation_id="debug-replan",
    )
    db_session.commit()

    items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
            )
        )
    )
    statuses = sorted(i.status for i in items)

    assert second_confirm.success is True
    assert "计划已确认" in (second_confirm.final_response or "")
    assert "active" in statuses
    assert "draft" not in statuses


def test_update_and_delete_event(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug-update",
    )
    db_session.commit()

    initial_reminders = list(
        db_session.scalars(
            select(ReminderJob)
            .where(
                ReminderJob.user_id == owner.id,
                ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
            )
            .order_by(ReminderJob.created_at.asc())
        )
    )
    assert len(initial_reminders) == 1
    assert initial_reminders[0].status == "pending"

    update_state = graph.invoke(
        current_user=owner,
        message="把明天下午 3 点的会议改到 4 点",
        conversation_id="debug-update",
    )
    db_session.commit()

    updated_event = db_session.scalar(
        select(ScheduledItem).where(ScheduledItem.user_id == owner.id)
    )
    updated_reminders = list(
        db_session.scalars(
            select(ReminderJob)
            .where(
                ReminderJob.user_id == owner.id,
                ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
            )
            .order_by(ReminderJob.created_at.asc())
        )
    )
    assert "4 点" in (update_state.final_response or "")
    assert updated_event is not None
    assert _local_hour(updated_event.start_time) == 16
    assert len(updated_reminders) == 2
    assert updated_reminders[0].status == "canceled"
    assert updated_reminders[1].status == "pending"
    assert _local_hour(updated_reminders[1].trigger_time) == 16

    delete_prompt_state = graph.invoke(
        current_user=owner,
        message="删除明天下午 4 点的会议",
        conversation_id="debug-update",
    )
    db_session.commit()

    assert "删除" in (delete_prompt_state.final_response or "")

    delete_state = graph.invoke(
        current_user=owner,
        message="确认",
        conversation_id="debug-update",
    )
    db_session.commit()

    deleted_event = db_session.scalar(
        select(ScheduledItem).where(ScheduledItem.user_id == owner.id)
    )
    reminders_after_delete = list(
        db_session.scalars(
            select(ReminderJob)
            .where(
                ReminderJob.user_id == owner.id,
                ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
            )
            .order_by(ReminderJob.created_at.asc())
        )
    )

    assert "已删除" in (delete_state.final_response or "")
    assert deleted_event is not None
    assert deleted_event.status == "deleted"
    assert len(reminders_after_delete) == 2
    assert all(reminder.status == "canceled" for reminder in reminders_after_delete)


def test_conflict_clarification_and_cancel(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug-conflict",
    )
    db_session.commit()

    conflict_state = graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug-conflict",
    )
    db_session.commit()

    assert "冲突" in (conflict_state.final_response or "")

    shift_state = graph.invoke(
        current_user=owner,
        message="2",
        conversation_id="debug-conflict",
    )
    db_session.commit()

    shifted_event = db_session.scalar(
        select(ScheduledItem)
        .where(ScheduledItem.user_id == owner.id, ScheduledItem.status == "active")
        .order_by(ScheduledItem.start_time.desc())
    )
    shifted_reminder = db_session.scalar(
        select(ReminderJob)
        .where(
            ReminderJob.user_id == owner.id,
            ReminderJob.target_type == ReminderTargetType.SCHEDULED_ITEM.value,
            ReminderJob.status == "pending",
        )
        .order_by(ReminderJob.created_at.desc())
    )

    assert "顺延" in (shift_state.final_response or "")
    assert shifted_event is not None
    assert _local_hour(shifted_event.start_time) == 16
    assert shifted_reminder is not None
    assert _local_hour(shifted_reminder.trigger_time) == 16

    clarification_state = graph.invoke(
        current_user=owner,
        message="提醒我写论文",
        conversation_id="debug-clarify",
    )
    db_session.commit()

    assert "具体提醒时间" in (clarification_state.final_response or "")

    cancel_state = graph.invoke(
        current_user=owner, message="取消", conversation_id="debug-clarify"
    )
    db_session.commit()

    assert "已取消" in (cancel_state.final_response or "")
