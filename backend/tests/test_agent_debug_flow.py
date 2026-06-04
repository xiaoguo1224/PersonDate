from __future__ import annotations

from sqlalchemy import select

from app.models import (
    AgentPendingState,
    CalendarEvent,
    DayPlan,
    PendingStateStatus,
    ReminderJob,
    TaskItem,
)
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService


def _create_owner(db_session):
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            username="owner",
            password="password123",
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()
    db_session.refresh(owner)
    return owner


def test_create_event_and_reminder(db_session, graph) -> None:
    owner = _create_owner(db_session)

    state = graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    event = db_session.scalar(select(CalendarEvent).where(CalendarEvent.user_id == owner.id))
    reminder = db_session.scalar(select(ReminderJob).where(ReminderJob.user_id == owner.id))

    assert state.success is True
    assert state.intent == "create_event"
    assert "已为你创建日程" in (state.final_response or "")
    assert event is not None
    assert event.title == "会议"
    assert reminder is not None


def test_query_events_for_tomorrow(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    state = graph.invoke(current_user=owner, message="明天有什么安排？", conversation_id="debug")
    db_session.commit()

    assert state.intent == "query_events"
    assert "的安排" in (state.final_response or "")
    assert "会议" in (state.final_response or "")


def test_plan_task_and_confirm(db_session, graph) -> None:
    owner = _create_owner(db_session)

    state = graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug",
    )
    db_session.commit()

    task = db_session.scalar(select(TaskItem).where(TaskItem.user_id == owner.id))
    pending = db_session.scalar(
        select(AgentPendingState).where(
            AgentPendingState.user_id == owner.id,
            AgentPendingState.status == PendingStateStatus.ACTIVE.value,
        )
    )
    draft_plan = db_session.scalar(
        select(DayPlan).where(DayPlan.user_id == owner.id, DayPlan.status == "draft")
    )

    assert task is not None
    assert task.title == "写论文"
    assert state.pending_state is not None
    assert pending is not None
    assert draft_plan is not None

    confirm_state = graph.invoke(current_user=owner, message="确认", conversation_id="debug")
    db_session.commit()
    confirmed_plan = db_session.scalar(
        select(DayPlan).where(DayPlan.user_id == owner.id, DayPlan.status == "confirmed")
    )

    assert confirm_state.intent == "confirm_plan"
    assert "计划已确认" in (confirm_state.final_response or "")
    assert confirmed_plan is not None


def test_update_and_delete_event(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    update_state = graph.invoke(
        current_user=owner,
        message="把明天下午 3 点的会议改到 4 点",
        conversation_id="debug",
    )
    db_session.commit()

    updated_event = db_session.scalar(
        select(CalendarEvent).where(CalendarEvent.user_id == owner.id)
    )
    assert update_state.intent == "update_event"
    assert "4 点" in (update_state.final_response or "")
    assert updated_event is not None
    assert updated_event.start_time.hour == 16

    delete_state = graph.invoke(
        current_user=owner,
        message="删除明天下午 4 点的会议",
        conversation_id="debug",
    )
    db_session.commit()

    deleted_event = db_session.scalar(
        select(CalendarEvent).where(CalendarEvent.user_id == owner.id)
    )
    canceled_reminder = db_session.scalar(
        select(ReminderJob).where(ReminderJob.user_id == owner.id)
    )

    assert delete_state.intent == "delete_event"
    assert "已删除" in (delete_state.final_response or "")
    assert deleted_event is not None
    assert deleted_event.status == "deleted"
    assert canceled_reminder is not None
    assert canceled_reminder.status == "canceled"


def test_conflict_clarification_and_cancel(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    conflict_state = graph.invoke(
        current_user=owner,
        message="明天下午 3 点开会",
        conversation_id="debug",
    )
    db_session.commit()

    assert conflict_state.pending_state is not None
    assert "冲突" in (conflict_state.final_response or "")

    clarification_state = graph.invoke(
        current_user=owner,
        message="提醒我写论文",
        conversation_id="debug-clarify",
    )
    db_session.commit()

    assert clarification_state.pending_state is None
    assert "具体提醒时间" in (clarification_state.final_response or "")

    cancel_state = graph.invoke(
        current_user=owner, message="取消", conversation_id="debug-clarify"
    )
    db_session.commit()

    assert cancel_state.pending_state is None
    assert "已取消" in (cancel_state.final_response or "")
