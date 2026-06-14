from __future__ import annotations

from types import SimpleNamespace

from app.core.config import get_settings
from app.models import ChannelIdentity, User
from app.services.user_service import UserService


def _auth_headers() -> dict[str, str]:
    token = get_settings().wechat_channel_token
    return {"X-Channel-Token": token} if token else {}


def _seed_member(db_session):
    from app.schemas.setup import OwnerInitRequest
    from app.services.setup_service import SetupService

    settings = get_settings()
    SetupService(db_session).create_owner(
        OwnerInitRequest(display_name="主用户", email="owner@example.com")
    )
    member = UserService(db_session).create_user(
        username="member1",
        password="member123",
        role="member",
        display_name="成员一号",
    )
    db_session.commit()
    db_session.refresh(member)
    return member


class FakeGraph:
    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    def invoke(  # noqa: ANN001
        self,
        *,
        current_user: User,
        message: str,
        conversation_id: str = "debug",
        channel: str = "wechat",
    ):
        assert channel == "wechat"
        assert current_user.username == "member1"
        assert conversation_id == "wx_user_member"
        assert message == "明天下午 3 点开会"
        return SimpleNamespace(
            success=True,
            final_response="已为你创建安排：开会。",
            intent="create_scheduled_item",
            tool_calls=[{"tool_name": "create_scheduled_item"}],
            tool_results=[{"tool_name": "create_scheduled_item"}],
            graph_trace=["agent_loop"],
            error=None,
        )


def test_wechat_inbound_binding_success(monkeypatch, client, db_session) -> None:
    class _FakeClient:
        def get_channel_qr_code(self) -> dict[str, str]:
            return {"qr_img_content": "base64_fake", "qrcode_id": "qr_test_001"}

        def get_channel_qr_code_status(self, _: str) -> dict[str, object]:
            return {
                "status": "created",
                "bot_token": None,
                "base_url": None,
                "wechat_user_id": None,
            }

    monkeypatch.setattr(
        "app.api.routes.wechat.build_wechat_channel_client",
        lambda: _FakeClient(),
    )
    monkeypatch.setattr("app.api.routes.wechat.SchedulePlanningGraph", FakeGraph)

    member = _seed_member(db_session)
    from app.services.auth_service import AuthService
    from app.schemas.auth import LoginRequest
    auth = AuthService(db_session)
    _, member_token = auth.login(LoginRequest(username="member1", password="member123"))
    db_session.commit()

    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["data"]["login_session_id"]

    confirm_response = client.post(
        f"/api/me/wechat-login-sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "account_id": "wx_account_member",
            "wechat_user_id": "wx_user_member",
            "bot_token": "token_member",
            "base_url": "https://wechat.example.com",
            "remark": "成员微信",
        },
    )
    assert confirm_response.status_code == 200

    inbound_response = client.post(
        "/api/wechat/inbound",
        headers=_auth_headers(),
        json={
            "message_id": "wx_msg_bind_1",
            "conversation_id": "wx_user_member",
            "channel_user_id": "wx_user_member",
            "display_name": "成员一号",
            "content_type": "text",
            "content": "明天下午 3 点开会",
            "raw_payload": {},
        },
    )

    assert inbound_response.status_code == 200
    body = inbound_response.json()
    assert body["success"] is True
    assert body["data"]["reply"].startswith("已为你创建安排：开会")

    identity_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert identity_response.status_code == 200
    assert len(identity_response.json()["data"]["items"]) == 1
    assert identity_response.json()["data"]["items"][0]["channel_user_id"] == "wx_user_member"


def test_wechat_inbound_unbound_prompt(client) -> None:
    response = client.post(
        "/api/wechat/inbound",
        headers=_auth_headers(),
        json={
            "message_id": "wx_msg_unbound_1",
            "conversation_id": "wx_user_unbound",
            "channel_user_id": "wx_user_unbound",
            "display_name": "未绑定用户",
            "content_type": "text",
            "content": "明天下午 3 点开会",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    expected_reply = "你还没有绑定账号，请先在 Web 中创建二维码登录会话并完成微信确认。"
    assert body["data"]["reply"] == expected_reply


def test_wechat_inbound_routes_to_agent_graph(monkeypatch, client, db_session) -> None:
    member = _seed_member(db_session)
    db_session.add(
        ChannelIdentity(
            user_id=member.id,
            channel="wechat",
            channel_user_id="wx_user_member",
            conversation_id="wx_user_member",
            display_name="成员一号",
            status="active",
        )
    )
    db_session.commit()

    monkeypatch.setattr("app.api.routes.wechat.SchedulePlanningGraph", FakeGraph)

    response = client.post(
        "/api/wechat/inbound",
        headers=_auth_headers(),
        json={
            "message_id": "wx_msg_route_1",
            "conversation_id": "wx_user_member",
            "channel_user_id": "wx_user_member",
            "display_name": "成员一号",
            "content_type": "text",
            "content": "明天下午 3 点开会",
            "raw_payload": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["reply"] == "已为你创建安排：开会。"
