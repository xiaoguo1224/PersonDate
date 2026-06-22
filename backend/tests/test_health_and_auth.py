from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import verify_password
from app.main import create_app
from app.models import UserRole
from app.schemas.auth import LoginRequest, RegisterWithInviteRequest
from app.schemas.invite_code import InviteCodeCreateRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.invite_code_service import InviteCodeService
from app.services.setup_service import SetupService


def test_health_endpoint() -> None:
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_owner_init_and_login(db_session) -> None:
    settings = get_settings()
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()

    assert owner.username == "admin"
    assert owner.role == UserRole.OWNER.value
    assert verify_password(settings.admin_password, owner.password_hash)

    auth = AuthService(db_session)
    user, token, refresh_token = auth.login(
        LoginRequest(username="admin", password=settings.admin_password)
    )
    db_session.commit()

    assert user.id == owner.id
    assert token
    assert refresh_token


def test_register_with_invite(db_session) -> None:
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()

    invite_service = InviteCodeService(db_session)
    invite_code = invite_service.create(
        owner,
        payload=InviteCodeCreateRequest(max_uses=1, expires_at=None, remark="test"),
    )
    db_session.commit()

    auth = AuthService(db_session)
    user, token, refresh_token = auth.register_with_invite(
        RegisterWithInviteRequest(
            invite_code=invite_code.code,
            username="user1",
            password="password123",
            display_name="用户1",
            email="user1@example.com",
        )
    )
    db_session.commit()

    assert user.username == "user1"
    assert token
    assert refresh_token


def test_register_with_invite_allows_blank_optional_fields(db_session) -> None:
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()

    invite_service = InviteCodeService(db_session)
    invite_code = invite_service.create(
        owner,
        payload=InviteCodeCreateRequest(max_uses=1, expires_at=None, remark="test"),
    )
    db_session.commit()

    auth = AuthService(db_session)
    user, token, refresh_token = auth.register_with_invite(
        RegisterWithInviteRequest(
            invite_code=invite_code.code,
            username="user2",
            password="password123",
            display_name="",
            email="",
        )
    )
    db_session.commit()

    assert user.username == "user2"
    assert user.display_name is None
    assert user.email is None
    assert token
    assert refresh_token


def test_auth_access_refresh_and_logout_flow(client: TestClient, db_session) -> None:
    settings = get_settings()
    setup = SetupService(db_session)
    setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()

    login_response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": get_settings().admin_password},
    )
    assert login_response.status_code == 200
    assert login_response.cookies.get("schedule-agent.refresh-token")
    assert (
        f"Max-Age={settings.auth_cookie_max_age_seconds}"
        in login_response.headers.get("set-cookie", "")
    )

    access_token = login_response.json()["data"]["access_token"]
    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["username"] == "admin"

    refresh_response = client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200
    refreshed_access_token = refresh_response.json()["data"]["access_token"]
    assert refreshed_access_token
    assert refreshed_access_token != access_token

    refreshed_me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {refreshed_access_token}"},
    )
    assert refreshed_me_response.status_code == 200
    assert refreshed_me_response.json()["data"]["username"] == "admin"

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    set_cookie_header = logout_response.headers.get("set-cookie", "")
    assert "schedule-agent.refresh-token=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header

    refresh_after_logout = client.post("/api/auth/refresh")
    assert refresh_after_logout.status_code == 401


def test_agent_create_event(db_session, graph) -> None:
    setup = SetupService(db_session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    db_session.commit()
    db_session.refresh(owner)

    state = graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    assert state.success is True
    assert "已为你创建安排" in (state.final_response or "")
    assert state.intent == "create_scheduled_item"
    assert state.tool_calls
