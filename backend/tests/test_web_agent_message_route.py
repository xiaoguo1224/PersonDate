from __future__ import annotations

from types import SimpleNamespace


class FakeGraph:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    def invoke(self, *, current_user, message: str, conversation_id: str = "debug", channel: str = "wechat"):  # noqa: ANN001
        assert channel == "web"
        assert conversation_id.startswith("web:")
        assert message == "明天下午 3 点开会"
        assert current_user.username == "admin"
        return SimpleNamespace(
            success=True,
            final_response="已为你创建安排：开会。",
            intent="create_scheduled_item",
            tool_calls=[{"tool_name": "create_scheduled_item"}],
            tool_results=[{"tool_name": "create_scheduled_item"}],
            graph_trace=["agent_loop"],
            error=None,
        )


class CrashGraph:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        pass

    def invoke(self, *, current_user, message: str, conversation_id: str = "debug", channel: str = "wechat"):  # noqa: ANN001
        raise RuntimeError("LLM 服务不可用")


class InitCrashGraph:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise RuntimeError("缺少大模型凭据")


def test_web_agent_message_route_uses_web_channel(monkeypatch, client, admin_token) -> None:
    monkeypatch.setattr("app.api.routes.agent.SchedulePlanningGraph", FakeGraph)

    response = client.post(
        "/api/me/agent/message",
        json={"message": "明天下午 3 点开会"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["intent"] == "create_scheduled_item"
    assert body["data"]["graph_trace"] == ["agent_loop"]


def test_web_agent_message_route_returns_llm_error_detail(monkeypatch, client, admin_token) -> None:
    monkeypatch.setattr("app.api.routes.agent.SchedulePlanningGraph", CrashGraph)

    response = client.post(
        "/api/me/agent/message",
        json={"message": "明天下午 3 点开会"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
    assert "LLM 服务不可用" in body["detail"]


def test_web_agent_message_route_returns_init_error_detail(monkeypatch, client, admin_token) -> None:
    monkeypatch.setattr("app.api.routes.agent.SchedulePlanningGraph", InitCrashGraph)

    response = client.post(
        "/api/me/agent/message",
        json={"message": "明天下午 3 点开会"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
    assert "缺少大模型凭据" in body["detail"]
