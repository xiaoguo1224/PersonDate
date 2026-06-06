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
    user, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    db_session.commit()

    assert user.id == owner.id
    assert token


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
    user, token = auth.register_with_invite(
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
    user, token = auth.register_with_invite(
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
    assert state.intent == "create_event"
    assert state.tool_calls
