from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    ContentType,
    MessageDirection,
    WechatChannelOutboundMessage,
)
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService
from app.services.user_service import UserService


def _build_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app, session


def _login(session, username: str, password: str) -> str:  # noqa: ANN001
    auth = AuthService(session)
    _, token = auth.login(LoginRequest(username=username, password=password))
    session.commit()
    return token


def _seed_users(session):  # noqa: ANN001
    settings = get_settings()
    setup = SetupService(session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    member = UserService(session).create_user(
        username="member1",
        password="member123",
        role="member",
        display_name="成员一号",
    )
    session.commit()
    session.refresh(owner)
    session.refresh(member)
    owner_token = _login(session, "admin", settings.admin_password)
    member_token = _login(session, "member1", "member123")
    return owner, member, owner_token, member_token


def test_wechat_login_session_and_unbind_flow() -> None:
    app, session = _build_client()
    _, member, _, member_token = _seed_users(session)

    client = TestClient(app)
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
            "account_id": "wx_account_001",
            "wechat_user_id": "wx_user_001",
            "bot_token": "token_001",
            "base_url": "https://wechat.example.com",
            "remark": "测试账号",
        },
    )

    assert confirm_response.status_code == 200

    account_response = client.get(
        "/api/me/wechat-accounts",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert account_response.status_code == 200
    account_body = account_response.json()
    assert len(account_body["data"]["items"]) == 1
    assert account_body["data"]["items"][0]["account_id"] == "wx_account_001"

    identity_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert identity_response.status_code == 200
    identity_body = identity_response.json()
    assert len(identity_body["data"]["items"]) == 1
    assert identity_body["data"]["items"][0]["channel_user_id"] == "wx_user_001"

    list_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert len(list_body["data"]["items"]) == 1
    assert list_body["data"]["items"][0]["channel_user_id"] == "wx_user_001"
    identity_id = list_body["data"]["items"][0]["id"]

    unbind_response = client.delete(
        f"/api/me/channel-identities/{identity_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert unbind_response.status_code == 200
    unbound_identity = session.get(ChannelIdentity, identity_id)
    assert unbound_identity is not None
    assert unbound_identity.status == "disabled"


def test_wechat_message_logs_and_status() -> None:
    app, session = _build_client()
    owner, member, owner_token, member_token = _seed_users(session)

    active_identity = ChannelIdentity(
        user_id=member.id,
        channel="wechat",
        channel_user_id="wx_user_member",
        conversation_id="wx_user_member",
        display_name="成员一号",
        status="active",
        bound_at=datetime.now(UTC),
    )
    owner_identity = ChannelIdentity(
        user_id=owner.id,
        channel="wechat",
        channel_user_id="wx_user_owner",
        conversation_id="wx_user_owner",
        display_name="主用户",
        status="active",
        bound_at=datetime.now(UTC),
    )
    session.add_all([active_identity, owner_identity])
    session.flush()

    inbound_log = ChannelMessageLog(
        user_id=member.id,
        channel="wechat",
        message_id="msg-in-1",
        conversation_id="wx_user_member",
        channel_user_id="wx_user_member",
        direction=MessageDirection.INBOUND.value,
        content_type=ContentType.TEXT.value,
        content="明天下午 3 点开会",
        context_token="ctx-in-1",
        raw_payload={"source": "wechat"},
        status="received",
    )
    outbound_log = ChannelMessageLog(
        user_id=owner.id,
        channel="wechat",
        message_id="msg-out-1",
        conversation_id="wx_user_owner",
        channel_user_id="wx_user_owner",
        direction=MessageDirection.OUTBOUND.value,
        content_type=ContentType.TEXT.value,
        content="提醒：15:00 项目会议即将开始。",
        context_token="ctx-out-1",
        raw_payload={"source": "worker"},
        status="sent",
        retry_count=0,
    )
    session.add_all([inbound_log, outbound_log])
    session.commit()

    status_response = TestClient(app).get(
        "/api/admin/wechat/status",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["success"] is True
    assert status_body["data"]["total_identities"] == 2
    assert status_body["data"]["active_identities"] == 2
    assert status_body["data"]["bound_users"] == 2
    assert len(status_body["data"]["recent_inbound_messages"]) == 1
    assert len(status_body["data"]["recent_outbound_messages"]) == 1
    assert status_body["data"]["recent_inbound_messages"][0]["context_token"] == "ctx-in-1"

    owner_logs_response = TestClient(app).get(
        "/api/admin/message-logs?direction=outbound",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_logs_response.status_code == 200
    owner_logs_body = owner_logs_response.json()
    assert len(owner_logs_body["data"]["items"]) == 1
    assert owner_logs_body["data"]["items"][0]["message_id"] == "msg-out-1"
    assert owner_logs_body["data"]["items"][0]["context_token"] == "ctx-out-1"
    assert owner_logs_body["data"]["items"][0]["retry_count"] == 0

    member_logs_response = TestClient(app).get(
        "/api/my-message-logs",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_logs_response.status_code == 200
    member_logs_body = member_logs_response.json()
    assert len(member_logs_body["data"]["items"]) == 1
    assert member_logs_body["data"]["items"][0]["message_id"] == "msg-in-1"


def test_admin_wechat_outbound_queue() -> None:
    app, session = _build_client()
    owner, _, owner_token, _ = _seed_users(session)

    account = ChannelIdentity(
        user_id=owner.id,
        channel="wechat",
        channel_user_id="wx_user_owner",
        conversation_id="wx_user_owner",
        display_name="主用户",
        status="active",
        bound_at=datetime.now(UTC),
    )
    session.add(account)
    session.flush()

    outbound = WechatChannelOutboundMessage(
        account_id="wx_account_001",
        message_id="msg-out-queue-1",
        to_user_id="wx_user_owner",
        conversation_id="wx_user_owner",
        content="提醒：会议即将开始。",
        context_token="ctx-out-queue-1",
        raw_payload={"source": "worker"},
        status="queued",
        retry_count=0,
    )
    session.add(outbound)
    session.commit()

    response = TestClient(app).get(
        "/api/admin/wechat/outbound-queue?status=queued",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["message_id"] == "msg-out-queue-1"
    assert body["data"]["items"][0]["status"] == "queued"
