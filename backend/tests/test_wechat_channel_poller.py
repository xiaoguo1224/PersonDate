from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import create_app
from app.models import WechatAccount
from app.schemas.wechat import WechatInboundResponse
from app.services.wechat_channel_adapter import WechatInboundHandlingResult
from app.services.wechat_channel_poller import WechatChannelPoller


def _build_session():
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
    return session


@dataclass
class FakeUpdatesClient:
    payload: dict[str, object]

    def get_updates(self, *, bot_token: str, cursor: str | None = None):  # noqa: ANN001
        assert bot_token == "token_001"
        assert cursor == "cursor_0"
        return self.payload


class FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, str | None]] = []

    def handle_inbound_message(self, payload, channel_token=None, *, require_auth=True):  # noqa: ANN001
        self.calls.append((payload.content, require_auth, payload.context_token))
        return WechatInboundHandlingResult(
            response=WechatInboundResponse(handled=True, reply="已处理"),
            message="已处理",
        )


class FlakyAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def handle_inbound_message(self, payload, channel_token=None, *, require_auth=True):  # noqa: ANN001
        self.calls.append(payload.message_id)
        if payload.message_id == "msg_001":
            raise RuntimeError("LLM 服务不可用")
        return WechatInboundHandlingResult(
            response=WechatInboundResponse(handled=True, reply="已处理"),
            message="已处理",
        )


def test_poll_account_once_updates_cursor_and_dispatches_messages() -> None:
    session = _build_session()
    account = WechatAccount(
        owner_user_id="owner-1",
        account_id="wx_account_001",
        wechat_user_id="wx_user_001",
        bot_token="token_001",
        base_url="https://wechat.example.com",
        cursor="cursor_0",
        status="active",
    )
    session.add(account)
    session.commit()

    adapter = FakeAdapter()
    client = FakeUpdatesClient(
        payload={
            "messages": [
                {
                    "message_id": "msg_001",
                    "from_user_id": "wx_user_001",
                    "to_user_id": "wx_account_001",
                    "session_id": "wx_user_001",
                    "display_name": "测试用户",
                    "message_type": "text",
                    "text": "明天下午 3 点开会",
                    "context_token": "ctx_001",
                }
            ],
            "get_updates_buf": "cursor_1",
        }
    )

    poller = WechatChannelPoller(session, client, adapter)
    processed = poller.poll_account_once("wx_account_001")

    assert processed == 1
    assert adapter.calls == [("明天下午 3 点开会", False, "ctx_001")]

    refreshed = session.get(WechatAccount, account.id)
    assert refreshed is not None
    assert refreshed.cursor == "cursor_1"
    assert refreshed.last_active_time is not None


def test_poll_account_once_marks_expired_on_auth_failure() -> None:
    session = _build_session()
    account = WechatAccount(
        owner_user_id="owner-1",
        account_id="wx_account_002",
        wechat_user_id="wx_user_002",
        bot_token="token_002",
        base_url="https://wechat.example.com",
        cursor="cursor_0",
        status="active",
    )
    session.add(account)
    session.commit()

    class ExpiredUpdatesClient:
        def get_updates(self, *, bot_token: str, cursor: str | None = None):  # noqa: ANN001
            request = httpx.Request("POST", "https://wechat.example.com/getupdates")
            response = httpx.Response(401, request=request, json={"error_message": "expired"})
            raise httpx.HTTPStatusError("expired", request=request, response=response)

    poller = WechatChannelPoller(session, ExpiredUpdatesClient(), FakeAdapter())
    processed = poller.poll_account_once("wx_account_002")

    assert processed == 0
    refreshed = session.get(WechatAccount, account.id)
    assert refreshed is not None
    assert refreshed.status == "expired"


def test_poll_account_once_continues_after_single_message_failure() -> None:
    session = _build_session()
    account = WechatAccount(
        owner_user_id="owner-1",
        account_id="wx_account_003",
        wechat_user_id="wx_user_003",
        bot_token="token_001",
        base_url="https://wechat.example.com",
        cursor="cursor_0",
        status="active",
    )
    session.add(account)
    session.commit()

    adapter = FlakyAdapter()
    client = FakeUpdatesClient(
        payload={
            "messages": [
                {
                    "message_id": "msg_001",
                    "from_user_id": "wx_user_001",
                    "to_user_id": "wx_account_003",
                    "session_id": "wx_user_001",
                    "display_name": "测试用户",
                    "message_type": "text",
                    "text": "坏消息",
                },
                {
                    "message_id": "msg_002",
                    "from_user_id": "wx_user_002",
                    "to_user_id": "wx_account_003",
                    "session_id": "wx_user_002",
                    "display_name": "测试用户2",
                    "message_type": "text",
                    "text": "好消息",
                },
            ],
            "get_updates_buf": "cursor_2",
        }
    )

    poller = WechatChannelPoller(session, client, adapter)
    processed = poller.poll_account_once("wx_account_003")

    assert processed == 1
    assert adapter.calls == ["msg_001", "msg_002"]

    refreshed = session.get(WechatAccount, account.id)
    assert refreshed is not None
    assert refreshed.cursor == "cursor_2"
