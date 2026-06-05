from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.models import ChannelIdentity, User
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


def _auth_headers() -> dict[str, str]:
    token = get_settings().wechat_channel_token
    return {"X-Channel-Token": token} if token else {}


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
            final_response="已为你创建日程：开会。",
            intent="create_event",
            tool_calls=[{"tool_name": "create_event"}],
            tool_results=[{"tool_name": "create_event"}],
            pending_state=None,
            graph_trace=[
                "load_context",
                "check_pending_state",
                "classify_intent",
                "extract_info",
                "generate_response",
            ],
            error=None,
        )


def test_wechat_inbound_binding_success() -> None:
    app, session = _build_client()
    _, member, _, member_token = _seed_users(session)

    client = TestClient(app)
    code_response = client.post(
        "/api/me/wechat-binding-code",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert code_response.status_code == 200
    code = code_response.json()["data"]["code"]

    inbound_response = client.post(
        "/api/wechat/inbound",
        headers=_auth_headers(),
        json={
            "message_id": "wx_msg_bind_1",
            "conversation_id": "wx_user_member",
            "channel_user_id": "wx_user_member",
            "display_name": "成员一号",
            "content_type": "text",
            "content": f"绑定 {code}",
            "raw_payload": {},
        },
    )

    assert inbound_response.status_code == 200
    body = inbound_response.json()
    assert body["success"] is True
    assert body["data"]["reply"] == "绑定成功，你现在可以通过微信使用日程 Agent 了。"

    identity_response = client.get(
        "/api/me/channel-identities",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert identity_response.status_code == 200
    assert len(identity_response.json()["data"]["items"]) == 1
    assert identity_response.json()["data"]["items"][0]["channel_user_id"] == "wx_user_member"


def test_wechat_inbound_unbound_prompt() -> None:
    app, _session = _build_client()
    client = TestClient(app)

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
    assert body["data"]["reply"] == "你还没有绑定账号，请先在 Web 中使用邀请码注册并绑定微信。"


def test_wechat_inbound_routes_to_agent_graph(monkeypatch) -> None:
    app, session = _build_client()
    _, member, _, _ = _seed_users(session)
    session.add(
        ChannelIdentity(
            user_id=member.id,
            channel="wechat",
            channel_user_id="wx_user_member",
            conversation_id="wx_user_member",
            display_name="成员一号",
            status="active",
        )
    )
    session.commit()

    monkeypatch.setattr("app.api.routes.wechat.SchedulePlanningGraph", FakeGraph)
    client = TestClient(app)

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
    assert body["data"]["reply"] == "已为你创建日程：开会。"
