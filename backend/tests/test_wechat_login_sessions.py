from __future__ import annotations

from sqlalchemy import select

from app.models import ChannelIdentity
from app.models.user import User


class _FakeChannelClient:
    def __init__(self) -> None:
        self.qr_img_content = "base64_fake_qr_image_data"
        self.qrcode_id = "qr_test_001"

    def get_channel_qr_code(self) -> dict[str, str]:
        return {
            "qr_img_content": self.qr_img_content,
            "qrcode_id": self.qrcode_id,
        }

    def get_channel_qr_code_status(self, qrcode_id: str) -> dict[str, object]:
        return {
            "status": "created",
            "bot_token": None,
            "base_url": None,
            "wechat_user_id": None,
        }


def test_create_and_fetch_wechat_login_session(monkeypatch, client, member_token) -> None:
    monkeypatch.setattr(
        "app.api.routes.wechat.build_wechat_channel_client",
        lambda: _FakeChannelClient(),
    )

    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["success"] is True
    assert create_body["data"]["login_session_id"].startswith("login_")
    assert create_body["data"]["qr_payload"].startswith("wechat-qr:")
    assert create_body["data"]["qr_img_content"] == "base64_fake_qr_image_data"
    assert create_body["data"]["status"] == "qr_created"
    assert "请使用微信扫码" in create_body["message"]

    session_id = create_body["data"]["login_session_id"]
    fetch_response = client.get(
        f"/api/me/wechat-login-sessions/{session_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert fetch_response.status_code == 200
    fetch_body = fetch_response.json()
    assert fetch_body["success"] is True
    assert fetch_body["data"]["login_session_id"] == session_id
    assert fetch_body["data"]["status"] == "qr_created"


def test_confirm_wechat_login_session_creates_account(monkeypatch, client, member_token) -> None:
    monkeypatch.setattr(
        "app.api.routes.wechat.build_wechat_channel_client",
        lambda: _FakeChannelClient(),
    )

    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    session_id = create_response.json()["data"]["login_session_id"]

    confirm_response = client.post(
        f"/api/me/wechat-login-sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "account_id": "wx_account_001",
            "wechat_user_id": "wx_user_001",
            "bot_token": "token_001",
            "base_url": "https://wechat.example.com",
            "remark": "测试账号",
        },
    )

    assert confirm_response.status_code == 200
    confirm_body = confirm_response.json()
    assert confirm_body["success"] is True
    assert confirm_body["data"]["status"] == "confirmed"
    assert confirm_body["data"]["confirmed_at"] is not None

    account_response = client.get(
        "/api/me/wechat-accounts",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert account_response.status_code == 200
    account_body = account_response.json()
    assert len(account_body["data"]["items"]) == 1
    account = account_body["data"]["items"][0]
    assert account["account_id"] == "wx_account_001"
    assert account["wechat_user_id"] == "wx_user_001"
    assert account["status"] == "active"


def test_confirm_wechat_login_session_binds_channel_identity(monkeypatch, client, member_token) -> None:
    monkeypatch.setattr(
        "app.api.routes.wechat.build_wechat_channel_client",
        lambda: _FakeChannelClient(),
    )

    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    session_id = create_response.json()["data"]["login_session_id"]

    confirm_response = client.post(
        f"/api/me/wechat-login-sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "account_id": "wx_account_002",
            "wechat_user_id": "wx_user_002",
            "bot_token": "token_002",
            "base_url": "https://wechat.example.com",
            "remark": "测试账号二",
        },
    )

    assert confirm_response.status_code == 200

    identity_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert identity_response.status_code == 200
    identity_body = identity_response.json()
    assert len(identity_body["data"]["items"]) == 1
    identity = identity_body["data"]["items"][0]
    assert identity["channel_user_id"] == "wx_user_002"
    assert identity["conversation_id"] == "wx_user_002"
    assert identity["status"] == "active"


def test_confirm_wechat_login_session_preserves_existing_identity_when_qr_only_returns_temp_account(
    monkeypatch,
    client,
    member_token,
    db_session,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.wechat.build_wechat_channel_client",
        lambda: _FakeChannelClient(),
    )
    member = db_session.scalar(select(User).where(User.username == "member1"))
    assert member is not None

    db_session.add(
        ChannelIdentity(
            user_id=member.id,
            channel="wechat",
            channel_user_id="o9cq80-stable@im.wechat",
            conversation_id="o9cq80-stable@im.wechat",
            display_name="旧微信会话",
            status="active",
        )
    )
    db_session.commit()

    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    session_id = create_response.json()["data"]["login_session_id"]

    confirm_response = client.post(
        f"/api/me/wechat-login-sessions/{session_id}/confirm",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "account_id": "qr_temp_account_001",
            "wechat_user_id": "qr_temp_account_001",
            "bot_token": "token_003",
            "base_url": "https://wechat.example.com",
            "remark": "重新绑定账号",
        },
    )

    assert confirm_response.status_code == 200

    identity_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert identity_response.status_code == 200
    items = identity_response.json()["data"]["items"]
    active_items = [item for item in items if item["status"] == "active"]

    assert len(active_items) == 1
    assert active_items[0]["channel_user_id"] == "o9cq80-stable@im.wechat"
    assert active_items[0]["conversation_id"] == "o9cq80-stable@im.wechat"
