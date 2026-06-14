from __future__ import annotations

from types import SimpleNamespace

from app.agent.graph import _resolve_llm_runtime_config, _resolve_timezone_name
from app.models import User
from app.schemas.system_setting import UpdateSystemSettingsRequest
from app.services.system_setting_service import SystemSettingService


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


def test_agent_runtime_llm_config_prefers_db_settings(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        "app.agent.graph.get_settings",
        lambda: SimpleNamespace(
            llm_base_url="https://env.example.com",
            llm_api_key="env-key",
            llm_model="env-model",
        ),
    )
    monkeypatch.setattr(
        "app.services.system_setting_service.get_settings",
        lambda: SimpleNamespace(jwt_secret="test-secret"),
    )

    service = SystemSettingService(db_session)
    service.update_settings(
        UpdateSystemSettingsRequest(
            LLM_BASE_URL="https://db.example.com",
            LLM_MODEL="db-model",
            LLM_API_KEY="db-key",
        )
    )
    db_session.commit()

    config = _resolve_llm_runtime_config(db_session)

    assert config["base_url"] == "https://db.example.com"
    assert config["api_key"] == "db-key"
    assert config["model"] == "db-model"


def test_agent_timezone_prefers_db_default_when_user_setting_missing(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        "app.agent.graph.get_settings",
        lambda: SimpleNamespace(default_timezone="Europe/London"),
    )
    monkeypatch.setattr(
        "app.services.system_setting_service.get_settings",
        lambda: SimpleNamespace(jwt_secret="test-secret"),
    )

    user = User(
        username="tz_user",
        display_name="TZ User",
        password_hash="hash",
        role="member",
        status="active",
    )
    db_session.add(user)
    db_session.flush()
    db_session.commit()

    service = SystemSettingService(db_session)
    service.update_settings(
        UpdateSystemSettingsRequest(DEFAULT_TIMEZONE="Asia/Shanghai")
    )
    db_session.commit()

    resolved = _resolve_timezone_name(user, db_session)

    assert resolved == "Asia/Shanghai"
