from __future__ import annotations

from sqlalchemy import select

from app.models import ReminderJob, ScheduledItem, TaskItem
from app.models.enums import ReminderTargetType
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService


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

    state = graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
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
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    state = graph.invoke(current_user=owner, message="明天有什么安排？", conversation_id="debug")
    db_session.commit()

    assert "的安排" in (state.final_response or "")
    assert "会议" in (state.final_response or "")


def test_plan_task_and_confirm(db_session, graph) -> None:
    owner = _create_owner(db_session)

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug",
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

    confirm_state = graph.invoke(current_user=owner, message="确认", conversation_id="debug")
    db_session.commit()
    confirmed_items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
                ScheduledItem.status == "active",
            )
        )
    )

    assert "计划已确认" in (confirm_state.final_response or "")
    assert len(confirmed_items) >= 1


def test_confirm_plan_replaces_existing_confirmed_plan(db_session, graph) -> None:
    owner = _create_owner(db_session)

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug",
    )
    db_session.commit()

    first_confirm = graph.invoke(current_user=owner, message="确认", conversation_id="debug")
    db_session.commit()
    assert first_confirm.success is True

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug",
    )
    db_session.commit()

    second_confirm = graph.invoke(current_user=owner, message="确认", conversation_id="debug")
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
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    update_state = graph.invoke(
        current_user=owner,
        message="把明天下午 3 点的会议改到 4 点",
        conversation_id="debug",
    )
    db_session.commit()

    updated_event = db_session.scalar(
        select(ScheduledItem).where(ScheduledItem.user_id == owner.id)
    )
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
        select(ScheduledItem).where(ScheduledItem.user_id == owner.id)
    )
    canceled_reminder = db_session.scalar(
        select(ReminderJob).where(ReminderJob.user_id == owner.id)
    )

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

    assert "冲突" in (conflict_state.final_response or "")

    shift_state = graph.invoke(current_user=owner, message="2", conversation_id="debug")
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
    assert shifted_event.start_time.hour == 16
    assert shifted_reminder is not None
    assert shifted_reminder.trigger_time.hour == 16

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
