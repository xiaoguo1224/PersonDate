from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.models import ChannelMessageLog
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService
from app.services.wechat_channel_service import WechatChannelService


class FakeWechatSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def send_text(self, conversation_id: str, content: str):  # noqa: ANN001
        self.calls.append((conversation_id, content))
        return {"success": True, "message_id": "wx_out_001"}


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


def _login_owner(session) -> str:  # noqa: ANN001
    settings = get_settings()
    setup = SetupService(session)
    setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    session.commit()
    auth = AuthService(session)
    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    session.commit()
    return token


def test_wechat_channel_service_send_text_records_outbound_log() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    sender = FakeWechatSender()

    session.add(
        ChannelMessageLog(
            user_id="owner-001",
            channel="wechat",
            message_id="wx_in_001",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="inbound",
            content_type="text",
            content="明天下午 3 点开会",
            context_token="ctx_001",
            raw_payload={"context_token": "ctx_001"},
            status="received",
        )
    )
    session.commit()

    service = WechatChannelService(session, sender=sender)
    log = service.send_text(conversation_id="wx_user_001", content="提醒：15:00 开会")
    session.commit()

    assert sender.calls == [("wx_user_001", "提醒：15:00 开会")]
    assert log.status == "sent"
    stored_log = session.scalar(session.query(ChannelMessageLog).filter_by(id=log.id).statement)
    assert stored_log is not None
    assert stored_log.direction == "outbound"
    assert stored_log.conversation_id == "wx_user_001"
    assert stored_log.content == "提醒：15:00 开会"
    assert stored_log.context_token == "ctx_001"
    assert stored_log.retry_count == 0
    assert stored_log.error_code is None


def test_wechat_channel_service_send_text_records_failed_outbound_log() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    class FailingWechatSender:
        def send_text(self, conversation_id: str, content: str, context_token: str | None = None):  # noqa: ANN001
            return {"success": False, "error_code": "TIMEOUT", "error_message": "timeout"}

    session.add(
        ChannelMessageLog(
            user_id="owner-001",
            channel="wechat",
            message_id="wx_in_002",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="inbound",
            content_type="text",
            content="明天下午 4 点开会",
            context_token="ctx_002",
            raw_payload={"context_token": "ctx_002"},
            status="received",
        )
    )
    session.commit()

    service = WechatChannelService(session, sender=FailingWechatSender())
    log = service.send_text(conversation_id="wx_user_001", content="提醒：16:00 开会")
    session.commit()

    assert log.status == "failed"
    assert log.retry_count == 1
    assert log.error_code == "TIMEOUT"
    assert log.error_message == "timeout"
    assert log.context_token == "ctx_002"


def test_admin_send_test_route_returns_send_result(monkeypatch) -> None:
    app, session = _build_client()
    owner_token = _login_owner(session)
    sender = FakeWechatSender()

    class FakeService(WechatChannelService):
        def __init__(self, db):  # noqa: ANN001
            super().__init__(db, sender=sender)

    monkeypatch.setattr("app.api.routes.wechat.WechatChannelService", FakeService)

    client = TestClient(app)
    response = client.post(
        "/api/admin/wechat/send-test",
        json={"conversation_id": "wx_user_001", "content": "测试消息"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["sent"] is True
    assert body["data"]["message_id"] == "wx_out_001"
