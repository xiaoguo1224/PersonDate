from __future__ import annotations


def test_admin_system_settings_list_and_update(client, admin_token) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}

    list_response = client.get(
        "/api/admin/system-settings",
        headers=headers,
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    keys = {item["key"] for item in items}
    assert {"DEFAULT_TIMEZONE", "LLM_MODEL", "LLM_API_KEY"}.issubset(keys)
    api_key_item = next(item for item in items if item["key"] == "LLM_API_KEY")
    assert api_key_item["value"] is None
    assert api_key_item["is_configured"] is False

    update_response = client.patch(
        "/api/admin/system-settings",
        headers=headers,
        json={
            "DEFAULT_TIMEZONE": "UTC",
            "LLM_BASE_URL": "https://api.example.com",
            "LLM_MODEL": "deepseek-chat",
            "LLM_API_KEY": "secret-key",
            "REMINDER_SCAN_INTERVAL_SECONDS": 15,
            "DEFAULT_REMIND_BEFORE_MINUTES": 20,
            "SYSTEM_DAILY_PUSH_ENABLED": True,
        },
    )
    assert update_response.status_code == 200
    updated_items = update_response.json()["data"]["items"]
    timezone_item = next(item for item in updated_items if item["key"] == "DEFAULT_TIMEZONE")
    assert timezone_item["value"] == "UTC"
    api_key_item = next(item for item in updated_items if item["key"] == "LLM_API_KEY")
    assert api_key_item["value"] is None
    assert api_key_item["is_configured"] is True
