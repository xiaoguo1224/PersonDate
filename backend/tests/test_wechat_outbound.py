from __future__ import annotations

import logging
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    User,
    WechatAccount,
    WechatChannelOutboundMessage,
)
from app.schemas.auth import LoginRequest
from app.services.auth_service import AuthService
from app.services.wechat_channel_service import WechatChannelService
from wechat_channel.ilink_client import ILinkClient, SendResult


def _make_owner_account_and_identity(db_session):
    user = User(
        username="owner_test",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    account = WechatAccount(
        owner_user_id=user.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    db_session.add(account)

    identity = ChannelIdentity(
        user_id=user.id,
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    db_session.add(identity)
    db_session.flush()
    return user, account, identity


def _mock_ilink_client() -> MagicMock:
    client = MagicMock(spec=ILinkClient)
    client.get_typing_ticket.return_value = None
    client.send_typing.return_value = None
    client.send_message.return_value = SendResult(success=True)
    return client


def test_wechat_channel_service_send_text_records_outbound_log(db_session) -> None:
    user, account, identity = _make_owner_account_and_identity(db_session)

    db_session.add(
        ChannelMessageLog(
            user_id=user.id,
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
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = SendResult(success=True)

    service = WechatChannelService(db_session)

    def _get_client():
        return mock_client

    service._get_ilink_client = _get_client  # type: ignore[method-assign]
    log = service.send_text(conversation_id="wx_user_001", content="提醒：15:00 开会")
    db_session.commit()

    assert log.status == "sent"
    assert log.error_code is None

    stored_log = db_session.scalar(
        db_session.query(ChannelMessageLog).filter_by(id=log.id).statement  # type: ignore[attr-defined]
    )
    assert stored_log is not None
    assert stored_log.direction == "outbound"
    assert stored_log.conversation_id == "wx_user_001"
    assert stored_log.content == "提醒：15:00 开会"


def test_wechat_channel_service_send_text_marks_queued_send_as_warning(
    db_session, caplog
) -> None:
    user, account, identity = _make_owner_account_and_identity(db_session)

    db_session.add(
        ChannelMessageLog(
            user_id=user.id,
            channel="wechat",
            message_id="wx_in_005",
            conversation_id="wx_user_001",
            channel_user_id="wx_user_001",
            direction="inbound",
            content_type="text",
            content="明天下午 7 点开会",
            context_token="ctx_005",
            raw_payload={"context_token": "ctx_005"},
            status="received",
        )
    )
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = SendResult(success=True, ret=-2, err_msg="queued")

    service = WechatChannelService(db_session)
    service._get_ilink_client = lambda: mock_client  # type: ignore[method-assign]

    with caplog.at_level(logging.WARNING):
        log = service.send_text(conversation_id="wx_user_001", content="提醒：19:00 开会")
    db_session.commit()

    assert log.status == "sent"
    assert log.error_code == "QUEUED"
    assert "等待确认送达" in (log.error_message or "")
    assert "微信消息已进入通道队列" in caplog.text

    stored_log = db_session.scalar(
        db_session.query(ChannelMessageLog).filter_by(id=log.id).statement  # type: ignore[attr-defined]
    )
    assert stored_log is not None
    assert stored_log.status == "sent"
    assert stored_log.error_code == "QUEUED"


def test_wechat_channel_service_send_text_records_failed_outbound_log(db_session) -> None:
    user, account, identity = _make_owner_account_and_identity(db_session)

    db_session.add(
        ChannelMessageLog(
            user_id=user.id,
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
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = SendResult(success=False, ret=-1, err_msg="mock error")

    service = WechatChannelService(db_session)
    service._get_ilink_client = lambda: mock_client  # type: ignore[method-assign]
    log = service.send_text(conversation_id="wx_user_001", content="提醒：16:00 开会")
    db_session.commit()

    assert log.status == "failed"
    assert log.error_code == "SEND_FAILED"
    assert "ret=-1" in log.error_message
    assert "err_msg=mock error" in log.error_message


def test_wechat_channel_service_send_text_creates_outbound_message_on_success(db_session) -> None:
    owner, account, identity = _make_owner_account_and_identity(db_session)  # noqa: F841

    db_session.add(
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
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = SendResult(success=True)

    service = WechatChannelService(db_session)
    service._get_ilink_client = lambda: mock_client  # type: ignore[method-assign]
    log = service.send_text(conversation_id="wx_user_001", content="提醒：18:00 开会")
    db_session.commit()

    assert log.status == "sent"

    stored_outbound = db_session.scalar(
        db_session.query(WechatChannelOutboundMessage)
        .filter_by(conversation_id="wx_user_001")
        .statement  # type: ignore[attr-defined]
    )
    assert stored_outbound is not None
    assert stored_outbound.status == "sent"
    assert stored_outbound.content == "提醒：18:00 开会"
    assert stored_outbound.context_token == "ctx_004"


def test_wechat_channel_dispatch_updates_outbound_and_message_logs(db_session) -> None:
    owner = User(
        username="owner_001",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    db_session.add(owner)
    db_session.flush()
    account = WechatAccount(
        owner_user_id=owner.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    db_session.add(account)
    db_session.add(
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
    db_session.add(
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
    db_session.commit()

    service = WechatChannelService(db_session)
    mock_client = _mock_ilink_client()
    service._get_ilink_client = lambda: mock_client  # type: ignore[method-assign]
    processed = service.dispatch_outbound_messages_once()
    db_session.commit()

    assert processed == 1
    assert mock_client.send_message.call_count == 1
    outbound_row = db_session.scalar(
        db_session.query(WechatChannelOutboundMessage).filter_by(message_id="wx_out_001").statement  # type: ignore[attr-defined]
    )
    assert outbound_row is not None
    assert outbound_row.status == "sent"
    assert outbound_row.sent_at is not None

    outbound_log = db_session.scalar(
        db_session.query(ChannelMessageLog).filter_by(message_id="wx_out_001").statement  # type: ignore[attr-defined]
    )
    assert outbound_log is not None
    assert outbound_log.status == "sent"
    assert outbound_log.retry_count == 0
    assert outbound_log.error_code is None
    assert outbound_log.error_message is None


def test_wechat_channel_service_send_text_retries_transient_errors(db_session) -> None:
    user, account, identity = _make_owner_account_and_identity(db_session)

    db_session.add(
        ChannelMessageLog(
            user_id=user.id,
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
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.side_effect = [
        TimeoutError("timeout"),
        TimeoutError("timeout"),
        SendResult(success=True),
    ]

    service = WechatChannelService(db_session)
    service._get_ilink_client = lambda: mock_client  # type: ignore[method-assign]
    log = service.send_text(conversation_id="wx_user_001", content="提醒：17:00 开会")
    db_session.commit()

    assert mock_client.send_message.call_count == 3
    assert log.status == "sent"
    assert log.retry_count == 2
    assert log.error_message is None


def test_admin_send_test_route_returns_send_result(monkeypatch, db_session) -> None:
    from app.api.deps import get_db
    from app.schemas.setup import OwnerInitRequest
    from app.services.setup_service import SetupService

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    SetupService(db_session).create_owner(
        OwnerInitRequest(display_name="主用户", email="owner@example.com")
    )
    auth = AuthService(db_session)
    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    db_session.commit()

    user = db_session.query(User).filter_by(role="owner").first()
    assert user is not None
    account = WechatAccount(
        owner_user_id=user.id,
        account_id="wx_account_admin_001",
        bot_token="bot_admin_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    db_session.add(account)
    identity = ChannelIdentity(
        user_id=user.id,
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    db_session.add(identity)
    db_session.commit()

    mock_client = _mock_ilink_client()
    mock_client.send_message.return_value = SendResult(success=True)

    monkeypatch.setattr(
        WechatChannelService,
        "_get_ilink_client",
        lambda self: mock_client,
    )

    client = TestClient(app)
    response = client.post(
        "/api/admin/wechat/send-test",
        json={"conversation_id": "wx_user_001", "content": "测试消息"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["sent"] is True
    assert body["data"]["status"] == "sent"
