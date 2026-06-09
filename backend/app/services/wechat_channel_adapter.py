from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph
from app.core.config import get_settings
from app.models import ChannelIdentity, WechatAccount
from app.schemas.wechat import WechatInboundRequest, WechatInboundResponse
from app.services.channel_identity_service import ChannelIdentityService
from app.services.user_service import UserService
from app.services.wechat_channel_service import WechatChannelService


@dataclass(slots=True)
class WechatInboundHandlingResult:
    response: WechatInboundResponse
    message: str


class WechatChannelAdapter:
    def __init__(
        self,
        db: Session,
        *,
        graph_cls: type[SchedulePlanningGraph] = SchedulePlanningGraph,
    ) -> None:
        self.db = db
        self.graph_cls = graph_cls

    def handle_inbound_message(
        self,
        payload: WechatInboundRequest,
        channel_token: str | None,
        *,
        require_auth: bool = True,
    ) -> WechatInboundHandlingResult:
        if require_auth:
            settings = get_settings()
            if settings.wechat_channel_token and channel_token != settings.wechat_channel_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="微信通道令牌无效",
                )

        service = WechatChannelService(self.db)
        identity_service = ChannelIdentityService(self.db)
        content = payload.content.strip()
        context_token = payload.context_token
        if context_token is None and payload.raw_payload is not None:
            raw_context_token = payload.raw_payload.get("context_token")
            context_token = raw_context_token if isinstance(raw_context_token, str) else None

        if payload.message_id and service.get_message_log_by_message_id(
            payload.message_id,
            account_id=payload.account_id,
        ):
            return WechatInboundHandlingResult(
                response=WechatInboundResponse(
                    handled=True,
                    reply="消息已处理，请勿重复发送。",
                ),
                message="消息已处理",
            )

        inbound_log = service.create_message_log(
            user_id=None,
            account_id=payload.account_id,
            message_id=payload.message_id,
            conversation_id=payload.conversation_id,
            channel_user_id=payload.channel_user_id,
            direction="inbound",
            content_type=payload.content_type,
            content=payload.content,
            context_token=context_token,
            raw_payload=payload.raw_payload,
        )

        if payload.content_type.lower() != "text":
            inbound_log.status = "ignored"
            inbound_log.error_message = "目前仅支持文本消息"
            self.db.commit()
            return WechatInboundHandlingResult(
                response=WechatInboundResponse(
                    handled=True,
                    reply="目前仅支持文本消息。",
                ),
                message="目前仅支持文本消息",
            )

        identity = (
            identity_service.get_active_by_channel_user_id(payload.channel_user_id)
            or identity_service.get_active_by_conversation_id(payload.conversation_id)
        )
        if identity is None and payload.account_id:
            account = self.db.scalar(
                select(WechatAccount).where(WechatAccount.account_id == payload.account_id)
            )
            if account is not None:
                identity = self.db.scalar(
                    select(ChannelIdentity).where(
                        ChannelIdentity.channel == "wechat",
                        ChannelIdentity.user_id == account.owner_user_id,
                        ChannelIdentity.status == "active",
                    )
                )
                if identity is not None:
                    identity.channel_user_id = payload.channel_user_id
                    identity.conversation_id = payload.conversation_id
                    self.db.flush()
        if identity is None:
            inbound_log.status = "unbound"
            inbound_log.error_message = "用户未绑定"
            self.db.commit()
            return WechatInboundHandlingResult(
                response=WechatInboundResponse(
                    handled=True,
                    reply="你还没有绑定账号，请先在 Web 中创建二维码登录会话并完成微信确认。",
                ),
                message="用户未绑定",
            )

        user = UserService(self.db).get_by_id(identity.user_id)
        if user is None or user.status != "active":
            inbound_log.user_id = identity.user_id
            inbound_log.status = "failed"
            inbound_log.error_message = "账号当前不可用"
            self.db.commit()
            return WechatInboundHandlingResult(
                response=WechatInboundResponse(
                    handled=True,
                    reply="你的账号当前不可用，请联系系统主用户。",
                ),
                message="账号当前不可用",
            )

        inbound_log.user_id = user.id
        graph = self.graph_cls(self.db)
        result = graph.invoke(
            current_user=user,
            message=content,
            conversation_id=payload.conversation_id,
            channel="wechat",
        )
        inbound_log.status = "processed" if result.get("success") else "failed"
        inbound_log.error_message = result.get("error")
        self.db.commit()
        final_response = result.get("final_response", "")
        return WechatInboundHandlingResult(
            response=WechatInboundResponse(
                handled=True,
                reply=final_response or "处理完成。",
            ),
            message=final_response or "处理完成",
        )
