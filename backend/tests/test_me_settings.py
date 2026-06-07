from __future__ import annotations


def test_get_and_update_my_settings(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    get_response = client.get("/api/me/settings", headers=headers)
    assert get_response.status_code == 200
    payload = get_response.json()["data"]
    assert payload["default_timezone"] == "Asia/Shanghai"
    assert payload["daily_plan_push_enabled"] is False

    update_response = client.patch(
        "/api/me/settings",
        headers=headers,
        json={
            "default_timezone": "UTC",
            "workday_start_time": "08:30:00",
            "workday_end_time": "17:30:00",
            "daily_plan_push_time": "07:45:00",
            "default_remind_before_minutes": 15,
            "daily_plan_push_enabled": True,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["default_timezone"] == "UTC"
    assert updated["daily_plan_push_enabled"] is True
