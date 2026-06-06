from __future__ import annotations

from unittest.mock import MagicMock

import pytest
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
    User,
    WechatAccount,
    WechatChannelOutboundMessage,
)
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService
from app.services.wechat_channel_service import WechatChannelService
from wechat_channel.ilink_client import ILinkClient


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


def _login_owner(session) -> str:
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


def _make_owner_account_and_identity(session):
    """Create an owner user, active WechatAccount and ChannelIdentity in one shot."""
    user = User(
        username="owner_test",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    session.add(user)
    session.flush()

    account = WechatAccount(
        owner_user_id=user.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    session.add(account)

    identity = ChannelIdentity(
        user_id=user.id,
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)
    session.flush()
    return user, account, identity


def _mock_ilink_client() -> MagicMock:
    """Return a MagicMock for ILinkClient with handy defaults."""
    client = MagicMock(spec=ILinkClient)
    client.get_typing_ticket.return_value = None
    client.send_typing.return_value = None
    client.send_message.return_value = True
    return client


def test_wechat_channel_service_send_text_records_outbound_log() -> None:
    """Verify send_text creates a ChannelMessageLog with 'sent' status on success."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    _make_owner_account_and_identity(session)

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

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = True

    service = WechatChannelService(session)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_get_ilink_client", lambda: mock_client)
        log = service.send_text(conversation_id="wx_user_001", content="提醒：15:00 开会")
    session.commit()

    assert log.status == "sent"
    assert log.error_code is None

    stored_log = session.scalar(
        session.query(ChannelMessageLog).filter_by(id=log.id).statement  # type: ignore[attr-defined]
    )
    assert stored_log is not None
    assert stored_log.direction == "outbound"
    assert stored_log.conversation_id == "wx_user_001"
    assert stored_log.content == "提醒：15:00 开会"


def test_wechat_channel_service_send_text_records_failed_outbound_log() -> None:
    """Verify send_text creates a failed log when ILinkClient.send_message fails."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    _make_owner_account_and_identity(session)

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

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = False

    service = WechatChannelService(session)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_get_ilink_client", lambda: mock_client)
        log = service.send_text(conversation_id="wx_user_001", content="提醒：16:00 开会")
    session.commit()

    assert log.status == "failed"
    assert log.error_code == "SEND_FAILED"
    assert log.error_message == "微信消息发送失败"


def test_wechat_channel_service_send_text_creates_outbound_message_on_success() -> None:
    """Verify send_text also writes a WechatChannelOutboundMessage row on success."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    owner, account, identity = _make_owner_account_and_identity(session)  # noqa: F841

    session.add(
        ChannelMessageLog(
            user_id=owner.id,
            channel="wechat",
            message_id="wx_in_004",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="inbound",
            content_type="text",
            content="明天下午 6 点开会",
            context_token="ctx_004",
            raw_payload={"context_token": "ctx_004"},
            status="received",
        )
    )
    session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = True

    service = WechatChannelService(session)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_get_ilink_client", lambda: mock_client)
        log = service.send_text(conversation_id="wx_user_001", content="提醒：18:00 开会")
    session.commit()

    assert log.status == "sent"

    stored_outbound = session.scalar(
        session.query(WechatChannelOutboundMessage)
        .filter_by(conversation_id="wx_user_001")
        .statement  # type: ignore[attr-defined]
    )
    assert stored_outbound is not None
    assert stored_outbound.status == "sent"
    assert stored_outbound.content == "提醒：18:00 开会"
    assert stored_outbound.context_token == "ctx_004"


def test_wechat_channel_dispatch_updates_outbound_and_message_logs() -> None:
    """dispatch_outbound_messages_once still works (independent of ILinkClient)."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    owner = User(
        username="owner_001",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    session.add(owner)
    session.flush()
    account = WechatAccount(
        owner_user_id=owner.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    session.add(account)
    session.add(
        ChannelMessageLog(
            user_id=owner.id,
            channel="wechat",
            account_id=account.account_id,
            message_id="wx_out_001",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="outbound",
            content_type="text",
            content="提醒：15:00 开会",
            context_token="ctx_001",
            raw_payload={"message_id": "wx_out_001"},
            status="queued",
            retry_count=0,
        )
    )
    session.add(
        WechatChannelOutboundMessage(
            account_id=account.account_id,
            message_id="wx_out_001",
            to_user_id="wx_user_001",
            conversation_id="wx_user_001",
            content="提醒：15:00 开会",
            context_token="ctx_001",
            raw_payload={"message_id": "wx_out_001"},
            status="queued",
            retry_count=0,
        )
    )
    session.commit()

    service = WechatChannelService(session)
    processed = service.dispatch_outbound_messages_once()
    session.commit()

    assert processed == 1
    outbound_row = session.scalar(
        session.query(WechatChannelOutboundMessage)
        .filter_by(message_id="wx_out_001")
        .statement  # type: ignore[attr-defined]
    )
    assert outbound_row is not None
    assert outbound_row.status == "sent"
    assert outbound_row.sent_at is not None

    outbound_log = session.scalar(
        session.query(ChannelMessageLog)
        .filter_by(message_id="wx_out_001")
        .statement  # type: ignore[attr-defined]
    )
    assert outbound_log is not None
    assert outbound_log.status == "sent"
    assert outbound_log.retry_count == 0
    assert outbound_log.error_code is None
    assert outbound_log.error_message is None


def test_wechat_channel_service_send_text_retries_transient_errors() -> None:
    """Verify send_text retries on transient (TimeoutError) failures."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    _make_owner_account_and_identity(session)

    session.add(
        ChannelMessageLog(
            user_id="owner-001",
            channel="wechat",
            message_id="wx_in_003",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="inbound",
            content_type="text",
            content="明天下午 5 点开会",
            context_token="ctx_003",
            raw_payload={"context_token": "ctx_003"},
            status="received",
        )
    )
    session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.side_effect = [
        TimeoutError("timeout"),
        TimeoutError("timeout"),
        True,
    ]

    service = WechatChannelService(session)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_get_ilink_client", lambda: mock_client)
        log = service.send_text(conversation_id="wx_user_001", content="提醒：17:00 开会")
    session.commit()

    assert mock_client.send_message.call_count == 3
    assert log.status == "sent"
    assert log.retry_count == 2
    assert log.error_message is None


def test_admin_send_test_route_returns_send_result(monkeypatch) -> None:
    """The /api/admin/wechat/send-test endpoint returns success when ILinkClient succeeds."""
    app, session = _build_client()
    owner_token = _login_owner(session)

    user = session.query(User).filter_by(role="owner").first()
    assert user is not None
    account = WechatAccount(
        owner_user_id=user.id,
        account_id="wx_account_admin_001",
        bot_token="bot_admin_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    session.add(account)
    identity = ChannelIdentity(
        user_id=user.id,
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)
    session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = True

    monkeypatch.setattr(
        WechatChannelService,
        "_get_ilink_client",
        lambda self: mock_client,
    )

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
    assert body["data"]["status"] == "sent"
