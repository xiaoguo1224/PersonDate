from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import ReminderJob, ScheduledItem, UserSettings
from app.services.reminder_service import ReminderService
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService


def test_list_tasks_returns_items(client, admin_token, owner, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    TaskService(db_session).create_task(
        user_id=owner.id,
        title="写论文",
        description=None,
        estimated_minutes=120,
        deadline=None,
        priority="high",
    )
    db_session.commit()

    response = client.get("/api/tasks", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"][0]["title"] == "写论文"


def test_create_task_generates_daily_scheduled_items_with_reminders(
    client, admin_token, owner, db_session
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    assert settings is not None
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 15
    db_session.commit()

    response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "晨间复盘",
            "estimated_minutes": 60,
            "priority": "high",
            "schedule_type": "daily",
            "start_date": "2099-07-01",
            "end_date": "2099-07-02",
            "time_type": "fixed",
            "scheduled_time": "08:00:00",
        },
    )

    assert response.status_code == 200
    task_id = response.json()["data"]["id"]

    scheduled_items = list(
        db_session.scalars(
            select(ScheduledItem)
            .where(ScheduledItem.source_task_id == task_id)
            .order_by(ScheduledItem.start_time)
        )
    )
    assert len(scheduled_items) == 2
    assert [item.remind_before_minutes for item in scheduled_items] == [15, 15]
    assert scheduled_items[0].start_time == datetime(2099, 7, 1, 0, 0, tzinfo=UTC)
    assert scheduled_items[1].start_time == datetime(2099, 7, 2, 0, 0, tzinfo=UTC)

    reminder_jobs = list(
        db_session.scalars(
            select(ReminderJob)
            .where(ReminderJob.target_id.in_([item.id for item in scheduled_items]))
            .order_by(ReminderJob.trigger_time)
        )
    )
    assert len(reminder_jobs) == 2
    assert [job.target_id for job in reminder_jobs] == [item.id for item in scheduled_items]
    assert reminder_jobs[0].trigger_time == datetime(2099, 6, 30, 23, 45, tzinfo=UTC)
    assert reminder_jobs[1].trigger_time == datetime(2099, 7, 1, 23, 45, tzinfo=UTC)


def test_list_reminders_returns_source_task_id(
    client, admin_token, owner, db_session
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    assert settings is not None
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 15
    db_session.commit()

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "晨间复盘",
            "estimated_minutes": 60,
            "priority": "high",
            "schedule_type": "daily",
            "start_date": "2099-07-01",
            "end_date": "2099-07-01",
            "time_type": "fixed",
            "scheduled_time": "08:00:00",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    response = client.get("/api/reminders", headers=headers)

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["source_task_id"] == task_id
    assert items[0]["target_type"] == "scheduled_item"


def test_clear_schedule_type_soft_deletes_items_and_cancels_reminders(
    client, admin_token, owner, db_session
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    assert settings is not None
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 15
    db_session.commit()

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "晨间复盘",
            "estimated_minutes": 60,
            "priority": "high",
            "schedule_type": "daily",
            "start_date": "2099-07-01",
            "end_date": "2099-07-01",
            "time_type": "fixed",
            "scheduled_time": "08:00:00",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    scheduled_item = db_session.scalar(
        select(ScheduledItem).where(ScheduledItem.source_task_id == task_id)
    )
    assert scheduled_item is not None
    reminder_job = db_session.scalar(
        select(ReminderJob).where(ReminderJob.target_id == scheduled_item.id)
    )
    assert reminder_job is not None
    assert reminder_job.status == "pending"

    update_response = client.patch(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "schedule_type": None,
            "start_date": None,
            "end_date": None,
            "time_type": None,
            "scheduled_time": None,
            "scheduled_end_time": None,
        },
    )

    assert update_response.status_code == 200
    db_session.refresh(scheduled_item)
    db_session.refresh(reminder_job)
    assert scheduled_item.status == "deleted"
    assert reminder_job.status == "canceled"


def test_clear_schedule_type_keeps_manual_items_with_same_source_task_id(
    client, admin_token, owner, db_session
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    assert settings is not None
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 15
    db_session.commit()

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "晨间复盘",
            "estimated_minutes": 60,
            "priority": "high",
            "schedule_type": "daily",
            "start_date": "2099-07-01",
            "end_date": "2099-07-01",
            "time_type": "fixed",
            "scheduled_time": "08:00:00",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    auto_item = db_session.scalar(
        select(ScheduledItem).where(
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.source == "task",
        )
    )
    assert auto_item is not None
    auto_reminder = db_session.scalar(
        select(ReminderJob).where(ReminderJob.target_id == auto_item.id)
    )
    assert auto_reminder is not None
    assert auto_reminder.status == "pending"

    manual_item = ScheduledItemService(db_session).create(
        user_id=owner.id,
        title="手动补充安排",
        start_time=datetime(2099, 7, 1, 2, 0, tzinfo=UTC),
        end_time=datetime(2099, 7, 1, 3, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
        source="manual",
        source_task_id=task_id,
        remind_before_minutes=10,
        status="active",
    )
    manual_reminder = ReminderService(db_session).sync_pending_for_scheduled_item(manual_item)
    assert manual_reminder is not None
    db_session.commit()

    update_response = client.patch(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "schedule_type": None,
            "start_date": None,
            "end_date": None,
            "time_type": None,
            "scheduled_time": None,
            "scheduled_end_time": None,
        },
    )

    assert update_response.status_code == 200
    db_session.refresh(auto_item)
    db_session.refresh(auto_reminder)
    db_session.refresh(manual_item)
    db_session.refresh(manual_reminder)
    assert auto_item.status == "deleted"
    assert auto_reminder.status == "canceled"
    assert manual_item.status == "active"
    assert manual_reminder.status == "pending"
