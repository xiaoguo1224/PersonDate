from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.models import User, WechatAccount
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
