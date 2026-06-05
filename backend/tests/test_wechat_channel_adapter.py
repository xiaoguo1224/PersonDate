from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.models import ChannelIdentity, ChannelMessageLog, User
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.schemas.wechat import WechatInboundRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService
from app.services.user_service import UserService
from app.services.wechat_channel_adapter import WechatChannelAdapter


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


def _login(session, username: str, password: str) -> str:  # noqa: ANN001
    auth = AuthService(session)
    _, token = auth.login(LoginRequest(username=username, password=password))
    session.commit()
    return token


def _seed_member(session):  # noqa: ANN001
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
    _login(session, "admin", settings.admin_password)
    return member


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
            graph_trace=["load_context", "generate_response"],
            error=None,
        )


def test_wechat_channel_adapter_handles_inbound_message() -> None:
    session = _build_session()
    member = _seed_member(session)
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

    adapter = WechatChannelAdapter(session, graph_cls=FakeGraph)
    result = adapter.handle_inbound_message(
        WechatInboundRequest(
            message_id="wx_msg_001",
            conversation_id="wx_user_member",
            channel_user_id="wx_user_member",
            content_type="text",
            content="明天下午 3 点开会",
            context_token="ctx_001",
            raw_payload={},
        ),
        channel_token=get_settings().wechat_channel_token,
    )

    assert result.response.handled is True
    assert result.response.reply == "已为你创建日程：开会。"
    assert result.message == "已为你创建日程：开会。"

    stored_log = session.scalar(
        session.query(ChannelMessageLog).filter_by(message_id="wx_msg_001").statement
    )
    assert stored_log is not None
    assert stored_log.context_token == "ctx_001"
