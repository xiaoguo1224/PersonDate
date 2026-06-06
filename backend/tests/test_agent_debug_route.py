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
from app.models import User
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService


class FakeGraph:
    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    def invoke(self, *, current_user: User, message: str, conversation_id: str = "debug", channel: str = "wechat"):  # noqa: ANN001,E501
        assert channel == "web"
        assert conversation_id == "debug"
        assert message == "明天下午 3 点开会"
        assert current_user.username == "admin"
        return SimpleNamespace(
            success=True,
            final_response="已为你创建安排：开会。",
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


def test_debug_message_route_uses_web_channel(monkeypatch) -> None:
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
    monkeypatch.setattr("app.api.routes.agent.SchedulePlanningGraph", FakeGraph)

    settings = get_settings()
    setup = SetupService(session)
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    session.commit()
    session.refresh(owner)

    auth = AuthService(session)
    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    session.commit()

    client = TestClient(app)
    response = client.post(
        "/api/agent/debug/message",
        json={"message": "明天下午 3 点开会"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["intent"] == "create_event"
    assert body["data"]["graph_trace"] == [
        "load_context",
        "check_pending_state",
        "classify_intent",
        "extract_info",
        "generate_response",
    ]
