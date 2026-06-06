from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.models import (
    ChannelIdentity,
    User,
    WechatAccount,
    WechatChannelInboundMessage,
)
from app.schemas.wechat_channel import WechatGetUpdatesResponse
from app.services.wechat_channel_service import WechatChannelService


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
    from app.wechat_channel_app import create_wechat_channel_app

    app = create_wechat_channel_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app, session


def test_wechat_channel_app_exposes_protocol_routes(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, _session = _build_client()
    owner = User(
        username="owner_1",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    _session.add(owner)
    _session.flush()
    account = WechatAccount(
        owner_user_id=owner.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    _session.add(account)
    _session.add(
        ChannelIdentity(
            user_id=owner.id,
            channel="wechat",
            channel_user_id="wx_1",
            conversation_id="wx_1",
            display_name="Owner",
            status="active",
        )
    )
    _session.commit()
    client = TestClient(app)

    assert client.post("/getupdates", json={"get_updates_buf": ""}).status_code == 200
    assert (
        client.post("/sendmessage", json={"to_user_id": "wx_1", "content": "hi"}).status_code
        == 200
    )
    assert client.post("/getconfig", json={}).status_code == 200
    assert (
        client.post("/sendtyping", json={"conversation_id": "wx_1", "typing": True}).status_code
        == 200
    )


def test_wechat_channel_app_getupdates_returns_seeded_messages(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, session = _build_client()
    owner = User(
        username="owner_1",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    session.add(owner)
    session.flush()
    service = WechatChannelService(session)
    account = WechatAccount(
        owner_user_id=owner.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    session.add(account)
    session.flush()
    service.enqueue_inbound_message(
        account_id=account.account_id,
        message_id="wx_msg_001",
        conversation_id="wx_conv_001",
        channel_user_id="wx_user_001",
        display_name="张三",
        content="明天下午 3 点开会",
        raw_payload={"message_id": "wx_msg_001"},
    )
    session.commit()

    client = TestClient(app)
    response = client.post(
        "/getupdates",
        json={"bot_token": "bot_001", "get_updates_buf": ""},
    )

    assert response.status_code == 200
    payload = WechatGetUpdatesResponse.model_validate(response.json())
    assert payload.messages[0].message_id == "wx_msg_001"
    assert payload.messages[0].content == "明天下午 3 点开会"
    assert payload.next_cursor is not None
    delivered = session.scalar(
        session.query(WechatChannelInboundMessage)
        .filter_by(message_id="wx_msg_001")
        .statement
    )
    assert delivered is not None
    assert delivered.status == "delivered"
    assert delivered.delivered_at is not None


def test_wechat_channel_app_ingest_message_makes_it_visible_to_getupdates(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, _session = _build_client()
    owner = User(
        username="owner_1",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    _session.add(owner)
    _session.flush()
    account = WechatAccount(
        owner_user_id=owner.id,
        account_id="wx_account_001",
        bot_token="bot_001",
        base_url="http://wechat-channel:18789",
        status="active",
    )
    _session.add(account)
    _session.commit()
    client = TestClient(app)

    ingest_response = client.post(
        "/ingest",
        json={
            "account_id": "wx_account_001",
            "message_id": "wx_msg_002",
            "conversation_id": "wx_conv_001",
            "channel_user_id": "wx_user_001",
            "display_name": "张三",
            "content_type": "text",
            "content": "明天有什么安排？",
            "raw_payload": {"message_id": "wx_msg_002"},
        },
    )
    assert ingest_response.status_code == 200
    ingest_payload = ingest_response.json()
    assert ingest_payload["account_id"] == "wx_account_001"
    assert ingest_payload["message_id"] == "wx_msg_002"

    updates_response = client.post(
        "/getupdates",
        json={"account_id": "wx_account_001", "get_updates_buf": ""},
    )

    assert updates_response.status_code == 200
    payload = WechatGetUpdatesResponse.model_validate(updates_response.json())
    assert payload.messages[0].message_id == "wx_msg_002"
    assert payload.messages[0].content == "明天有什么安排？"
    delivered = _session.scalar(
        _session.query(WechatChannelInboundMessage)
        .filter_by(message_id="wx_msg_002")
        .statement
    )
    assert delivered is not None
    assert delivered.status == "delivered"
    assert delivered.delivered_at is not None

    dedupe_response = client.post(
        "/ingest",
        json={
            "account_id": "wx_account_001",
            "message_id": "wx_msg_002",
            "conversation_id": "wx_conv_001",
            "channel_user_id": "wx_user_001",
            "display_name": "张三",
            "content_type": "text",
            "content": "明天有什么安排？",
            "raw_payload": {"message_id": "wx_msg_002"},
        },
    )
    assert dedupe_response.status_code == 200
    assert dedupe_response.json()["deduplicated"] is True


def test_wechat_channel_app_sendmessage_persists_outbound_record(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, session = _build_client()
    owner = User(
        username="owner_1",
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
        ChannelIdentity(
            user_id=owner.id,
            channel="wechat",
            channel_user_id="wx_user_001",
            conversation_id="wx_user_001",
            display_name="Owner",
            status="active",
        )
    )
    session.add(
        WechatAccount(
            owner_user_id=owner.id,
            account_id="wx_account_owner",
            bot_token="bot_owner",
            base_url="http://wechat-channel:18789",
            status="active",
        )
    )
    session.commit()
    client = TestClient(app)

    response = client.post(
        "/sendmessage",
        json={
            "to_user_id": "wx_user_001",
            "conversation_id": "wx_user_001",
            "content": "提醒：15:00 开会",
            "context_token": "ctx_out_001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message_id"] is not None
    assert "入队" in (body.get("detail") or "")

    outbound_row = session.execute(
        text(
            "select status, retry_count, sent_at from wechat_channel_outbound_messages limit 1"
        )
    ).one()
    assert outbound_row.status == "queued"
    assert outbound_row.retry_count == 0
    assert outbound_row.sent_at is None


def test_wechat_channel_app_dispatches_queued_outbound_messages(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module
    from app.core.scheduler import run_wechat_outbound_dispatch_scan

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, session = _build_client()
    owner = User(
        username="owner_1",
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
        ChannelIdentity(
            user_id=owner.id,
            channel="wechat",
            channel_user_id="wx_user_001",
            conversation_id="wx_user_001",
            display_name="Owner",
            status="active",
        )
    )
    session.commit()
    client = TestClient(app)

    response = client.post(
        "/sendmessage",
        json={
            "to_user_id": "wx_user_001",
            "conversation_id": "wx_user_001",
            "content": "提醒：15:00 开会",
            "context_token": "ctx_out_001",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message_id"] is not None

    processed = run_wechat_outbound_dispatch_scan(session_factory=lambda: session)
    session.commit()

    assert processed == 1
    outbound_row = session.execute(
        text(
            "select status, retry_count, sent_at from wechat_channel_outbound_messages limit 1"
        )
    ).one()
    assert outbound_row.status == "sent"
    assert outbound_row.retry_count == 0
    assert outbound_row.sent_at is not None


def test_wechat_channel_app_lists_outbound_messages(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, session = _build_client()
    owner = User(
        username="owner_1",
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
        ChannelIdentity(
            user_id=owner.id,
            channel="wechat",
            channel_user_id="wx_user_001",
            conversation_id="wx_user_001",
            display_name="Owner",
            status="active",
        )
    )
    session.commit()
    client = TestClient(app)

    send_response = client.post(
        "/sendmessage",
        json={
            "to_user_id": "wx_user_001",
            "conversation_id": "wx_user_001",
            "content": "提醒：15:00 开会",
            "context_token": "ctx_out_001",
        },
    )
    assert send_response.status_code == 200

    list_response = client.get("/outbound", params={"status": "queued"})

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["status"] == "queued"
    assert item["conversation_id"] == "wx_user_001"
    assert item["content"] == "提醒：15:00 开会"


def test_wechat_channel_app_getuploadurl(monkeypatch) -> None:
    from app import wechat_channel_routes as routes_module

    monkeypatch.setattr(
        routes_module,
        "get_settings",
        lambda: SimpleNamespace(wechat_channel_token=None),
    )
    app, session = _build_client()
    owner = User(
        username="owner_2",
        display_name="Owner",
        password_hash="hash",
        role="owner",
        status="active",
    )
    session.add(owner)
    session.flush()
    session.add(
        ChannelIdentity(
            user_id=owner.id,
            channel="wechat",
            channel_user_id="wx_user_owner",
            conversation_id="wx_user_owner",
            display_name="Owner",
            status="active",
        )
    )
    session.add(
        WechatAccount(
            owner_user_id=owner.id,
            account_id="wx_account_owner",
            bot_token="bot_owner",
            base_url="http://wechat-channel:18789",
            status="active",
        )
    )
    session.commit()
    client = TestClient(app)

    response = client.post(
        "/getuploadurl",
        json={
            "filekey": "file_001",
            "media_type": 3,
            "to_user_id": "wx_user_owner",
            "rawsize": 12345,
            "rawfilemd5": "0123456789abcdef0123456789abcdef",
            "filesize": 12352,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["ret"] == 0
    assert body["upload_param"]
