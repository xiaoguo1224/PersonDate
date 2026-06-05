from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.models import ChannelIdentity, UserStatus
from app.schemas.auth import LoginRequest, RegisterWithInviteRequest
from app.schemas.invite_code import InviteCodeCreateRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.invite_code_service import InviteCodeService
from app.services.setup_service import SetupService


def test_admin_users_manage_member_status_and_bindings() -> None:
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

    settings = get_settings()
    setup = SetupService(session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    session.commit()

    invite_service = InviteCodeService(session)
    invite = invite_service.create(
        owner,
        payload=InviteCodeCreateRequest(max_uses=1, expires_at=None, remark="member"),
    )
    session.commit()

    auth = AuthService(session)
    member, _ = auth.register_with_invite(
        RegisterWithInviteRequest(
            invite_code=invite.code,
            username="member1",
            password="password123",
            display_name="成员1",
            email="member1@example.com",
        )
    )
    session.commit()

    identity = ChannelIdentity(
        user_id=member.id,
        channel="wechat",
        channel_user_id="wx_member_1",
        conversation_id="wx_member_1",
        display_name="成员1",
        avatar_url=None,
        status="active",
        bound_at=datetime.now(UTC),
    )
    session.add(identity)
    session.commit()

    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    session.commit()

    client = TestClient(app)

    list_response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    users = list_response.json()["data"]["items"]
    assert any(item["username"] == "admin" for item in users)
    member_item = next(item for item in users if item["username"] == "member1")
    assert member_item["status"] == UserStatus.ACTIVE.value

    disable_response = client.patch(
        f"/api/admin/users/{member.id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["data"]["status"] == UserStatus.DISABLED.value

    enable_response = client.patch(
        f"/api/admin/users/{member.id}/enable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert enable_response.status_code == 200
    assert enable_response.json()["data"]["status"] == UserStatus.ACTIVE.value

    binding_response = client.get(
        f"/api/admin/users/{member.id}/channel-identities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert binding_response.status_code == 200
    bindings = binding_response.json()["data"]["items"]
    assert len(bindings) == 1
    assert bindings[0]["conversation_id"] == "wx_member_1"
