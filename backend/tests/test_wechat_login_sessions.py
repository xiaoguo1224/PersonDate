from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
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


def test_create_and_fetch_wechat_login_session() -> None:
    app, session = _build_client()
    _, member, _, member_token = _seed_users(session)

    client = TestClient(app)
    create_response = client.post(
        "/api/me/wechat-login-sessions",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert create_response.status_code == 200
    create_body = create_response.json()
    assert create_body["success"] is True
    assert create_body["data"]["login_session_id"].startswith("login_")
    assert create_body["data"]["qr_payload"].startswith("wechat-qr:")
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
    assert fetch_body["data"]["owner_user_id"] == member.id


def test_confirm_wechat_login_session_creates_account() -> None:
    app, session = _build_client()
    _, member, _, member_token = _seed_users(session)

    client = TestClient(app)
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


def test_confirm_wechat_login_session_binds_channel_identity() -> None:
    app, session = _build_client()
    _, member, _, member_token = _seed_users(session)

    client = TestClient(app)
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
