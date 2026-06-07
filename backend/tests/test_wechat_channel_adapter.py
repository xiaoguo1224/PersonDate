from __future__ import annotations

from types import SimpleNamespace

from app.core.config import get_settings
from app.models import ChannelIdentity, ChannelMessageLog, User
from app.schemas.wechat import WechatInboundRequest
from app.services.user_service import UserService
from app.services.wechat_channel_adapter import WechatChannelAdapter


def _seed_member(db_session):
    from app.schemas.setup import OwnerInitRequest
    from app.services.setup_service import SetupService

    settings = get_settings()
    SetupService(db_session).create_owner(
        OwnerInitRequest(display_name="主用户", email="owner@example.com")
    )
    member = UserService(db_session).create_user(
        username="member1",
        password="member123",
        role="member",
        display_name="成员一号",
    )
    db_session.commit()
    db_session.refresh(member)
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
            final_response="已为你创建安排：开会。",
            intent="create_scheduled_item",
            tool_calls=[{"tool_name": "create_scheduled_item"}],
            tool_results=[{"tool_name": "create_scheduled_item"}],
            pending_state=None,
            graph_trace=["load_context", "generate_response"],
            error=None,
        )


def test_wechat_channel_adapter_handles_inbound_message(db_session) -> None:
    member = _seed_member(db_session)
    db_session.add(
        ChannelIdentity(
            user_id=member.id,
            channel="wechat",
            channel_user_id="wx_user_member",
            conversation_id="wx_user_member",
            display_name="成员一号",
            status="active",
        )
    )
    db_session.commit()

    adapter = WechatChannelAdapter(db_session, graph_cls=FakeGraph)
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
    assert result.response.reply == "已为你创建安排：开会。"
    assert result.message == "已为你创建安排：开会。"

    stored_log = db_session.scalar(
        db_session.query(ChannelMessageLog).filter_by(message_id="wx_msg_001").statement
    )
    assert stored_log is not None
    assert stored_log.context_token == "ctx_001"
