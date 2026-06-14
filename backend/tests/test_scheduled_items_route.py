from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import ReminderJob, User


def test_create_scheduled_item_creates_reminder(client, admin_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.post(
        "/api/scheduled-items",
        headers=headers,
        json={
            "title": "手动创建会议",
            "description": "验证提醒同步",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 0,
            "source": "manual",
        },
    )

    assert response.status_code == 200
    item_id = response.json()["data"]["item"]["id"]
    owner_id = db_session.scalar(select(User.id).where(User.username == "admin"))

    reminder = db_session.scalar(
        select(ReminderJob).where(
            ReminderJob.user_id == owner_id,
            ReminderJob.target_id == item_id,
        )
    )

    assert reminder is not None
    assert reminder.title == "手动创建会议"
    assert reminder.trigger_time == datetime.fromisoformat("2026-06-06T15:00:00+08:00").astimezone(UTC)


def test_list_reminders_supports_trigger_time_sort_order(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    for payload in (
        {
            "title": "较早提醒",
            "description": "排序测试",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
            "source": "manual",
        },
        {
            "title": "较晚提醒",
            "description": "排序测试",
            "start_time": "2026-06-06T18:00:00+08:00",
            "end_time": "2026-06-06T19:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
            "source": "manual",
        },
    ):
        response = client.post("/api/scheduled-items", headers=headers, json=payload)
        assert response.status_code == 200

    asc_response = client.get(
        "/api/reminders?status=pending&page=1&page_size=10&sort_order=trigger_time_asc",
        headers=headers,
    )
    desc_response = client.get(
        "/api/reminders?status=pending&page=1&page_size=10&sort_order=trigger_time_desc",
        headers=headers,
    )

    assert asc_response.status_code == 200
    assert desc_response.status_code == 200
    assert [item["title"] for item in asc_response.json()["data"]["items"]] == ["较早提醒", "较晚提醒"]
    assert [item["title"] for item in desc_response.json()["data"]["items"]] == ["较晚提醒", "较早提醒"]
