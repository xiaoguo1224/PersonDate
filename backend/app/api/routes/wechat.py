from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph
from app.api.deps import get_current_user, get_db, require_owner
from app.core.config import get_settings
from app.models import ChannelIdentity, ChannelMessageLog, User, WechatAccount, WechatLoginSession
from app.schemas.common import ApiResponse
from app.schemas.wechat import (
    ChannelIdentityItem,
    ChannelIdentityListResponse,
    ChannelMessageLogItem,
    ChannelMessageLogListResponse,
    WechatAccountItem,
    WechatAccountListResponse,
    WechatInboundRequest,
    WechatInboundResponse,
    WechatLoginSessionConfirmRequest,
    WechatLoginSessionCreateResponse,
    WechatLoginSessionItem,
    WechatSendTextRequest,
    WechatSendTextResponse,
    WechatStatusResponse,
)
from app.services.channel_identity_service import ChannelIdentityService
from app.services.user_service import UserService
from app.services.wechat_channel_service import WechatChannelService

router = APIRouter(tags=["wechat"])


def _to_identity_item(identity: ChannelIdentity) -> ChannelIdentityItem:
    return ChannelIdentityItem(
        id=identity.id,
        user_id=identity.user_id,
        channel=identity.channel,
        channel_user_id=identity.channel_user_id,
        conversation_id=identity.conversation_id,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
        status=identity.status,
        bound_at=identity.bound_at,
        created_at=identity.created_at,
    )


def _to_message_log_item(log: ChannelMessageLog) -> ChannelMessageLogItem:
    return ChannelMessageLogItem(
        id=log.id,
        user_id=log.user_id,
        channel=log.channel,
        account_id=log.account_id,
        message_id=log.message_id,
        conversation_id=log.conversation_id,
        channel_user_id=log.channel_user_id,
        direction=log.direction,
        content_type=log.content_type,
        content=log.content,
        raw_payload=log.raw_payload,
        status=log.status,
        error_message=log.error_message,
        created_at=log.created_at,
    )


def _validate_channel_token(channel_token: str | None) -> None:
    settings = get_settings()
    if settings.wechat_channel_token and channel_token != settings.wechat_channel_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="微信通道令牌无效")


def _to_login_session_item(session: WechatLoginSession) -> WechatLoginSessionItem:
    return WechatLoginSessionItem(
        id=session.id,
        owner_user_id=session.owner_user_id,
        login_session_id=session.login_session_id,
        qr_payload=session.qr_payload,
        status=session.status,
        expires_at=session.expires_at,
        confirmed_at=session.confirmed_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _to_account_item(account: WechatAccount) -> WechatAccountItem:
    return WechatAccountItem(
        id=account.id,
        owner_user_id=account.owner_user_id,
        account_id=account.account_id,
        wechat_user_id=account.wechat_user_id,
        base_url=account.base_url,
        cursor=account.cursor,
        remark=account.remark,
        status=account.status,
        bind_time=account.bind_time,
        last_active_time=account.last_active_time,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.post("/me/wechat-login-sessions")
def create_wechat_login_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatLoginSessionCreateResponse]:
    service = WechatChannelService(db)
    session = service.create_login_session(current_user.id)
    db.commit()
    return ApiResponse(
        data=WechatLoginSessionCreateResponse(
            login_session_id=session.login_session_id,
            qr_payload=session.qr_payload,
            expires_at=session.expires_at,
            status=session.status,
        ),
        message="请使用微信扫码完成登录",
    )


@router.get("/me/wechat-login-sessions/{login_session_id}")
def get_my_wechat_login_session(
    login_session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatLoginSessionItem]:
    service = WechatChannelService(db)
    session = service.get_login_session(
        owner_user_id=current_user.id,
        login_session_id=login_session_id,
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="登录会话不存在")
    return ApiResponse(data=_to_login_session_item(session))


@router.post("/me/wechat-login-sessions/{login_session_id}/confirm")
def confirm_wechat_login_session(
    login_session_id: str,
    payload: WechatLoginSessionConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatLoginSessionItem]:
    service = WechatChannelService(db)
    try:
        session, account = service.confirm_login_session(
            owner_user_id=current_user.id,
            login_session_id=login_session_id,
            account_id=payload.account_id,
            wechat_user_id=payload.wechat_user_id,
            bot_token=payload.bot_token,
            base_url=payload.base_url,
            remark=payload.remark,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    return ApiResponse(
        data=_to_login_session_item(session),
        message=f"微信账号 {account.account_id} 已确认绑定",
    )


@router.get("/me/channel-identities")
def list_my_channel_identities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChannelIdentityListResponse]:
    service = WechatChannelService(db)
    items = [_to_identity_item(identity) for identity in service.list_identities(current_user.id)]
    return ApiResponse(data=ChannelIdentityListResponse(items=items))


@router.get("/me/wechat-accounts")
def list_my_wechat_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatAccountListResponse]:
    service = WechatChannelService(db)
    items = [_to_account_item(account) for account in service.list_accounts(current_user.id)]
    return ApiResponse(data=WechatAccountListResponse(items=items))


@router.delete("/me/channel-identities/{identity_id}")
def disable_my_channel_identity(
    identity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChannelIdentityItem]:
    service = WechatChannelService(db)
    identity = service.disable_identity(current_user.id, identity_id)
    if identity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="绑定记录不存在")
    db.commit()
    return ApiResponse(data=_to_identity_item(identity), message="已解绑微信")


@router.get("/my-message-logs")
def list_my_message_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> ApiResponse[ChannelMessageLogListResponse]:
    service = WechatChannelService(db)
    items = [
        _to_message_log_item(log)
        for log in service.list_message_logs(
            user_id=current_user.id,
            account_id=account_id,
            conversation_id=conversation_id,
            direction=direction,
            limit=limit,
        )
    ]
    return ApiResponse(data=ChannelMessageLogListResponse(items=items))


@router.get("/admin/wechat/status")
def get_wechat_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[WechatStatusResponse]:
    service = WechatChannelService(db)
    summary = service.get_status_summary()
    return ApiResponse(
        data=WechatStatusResponse(
            connected=summary["connected"],
            channel_token_configured=summary["channel_token_configured"],
            total_accounts=summary["total_accounts"],
            active_accounts=summary["active_accounts"],
            total_identities=summary["total_identities"],
            active_identities=summary["active_identities"],
            bound_users=summary["bound_users"],
            last_message_at=summary["last_message_at"],
            recent_inbound_messages=[
                _to_message_log_item(log) for log in summary["recent_inbound_messages"]
            ],
            recent_outbound_messages=[
                _to_message_log_item(log) for log in summary["recent_outbound_messages"]
            ],
        )
    )


@router.get("/admin/message-logs")
def list_admin_message_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
    account_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> ApiResponse[ChannelMessageLogListResponse]:
    service = WechatChannelService(db)
    items = [
        _to_message_log_item(log)
        for log in service.list_message_logs(
            account_id=account_id,
            conversation_id=conversation_id,
            direction=direction,
            limit=limit,
        )
    ]
    return ApiResponse(data=ChannelMessageLogListResponse(items=items))


@router.post("/admin/wechat/send-test")
def send_wechat_test_message(
    payload: WechatSendTextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[WechatSendTextResponse]:
    service = WechatChannelService(db)
    log = service.send_text(
        conversation_id=payload.conversation_id,
        content=payload.content,
        user_id=current_user.id,
    )
    db.commit()
    return ApiResponse(
        data=WechatSendTextResponse(
            sent=log.status == "sent",
            conversation_id=log.conversation_id,
            content=log.content or payload.content,
            message_id=log.message_id,
            error_message=log.error_message,
        ),
        message="测试消息已发送" if log.status == "sent" else "测试消息发送失败",
    )


@router.post("/wechat/inbound")
def inbound_wechat_message(
    payload: WechatInboundRequest,
    db: Session = Depends(get_db),
    channel_token: str | None = Header(default=None, alias="X-Channel-Token"),
) -> ApiResponse[WechatInboundResponse]:
    _validate_channel_token(channel_token)

    service = WechatChannelService(db)
    identity_service = ChannelIdentityService(db)
    content = payload.content.strip()

    if payload.message_id and service.get_message_log_by_message_id(
        payload.message_id,
        account_id=payload.account_id,
    ):
        return ApiResponse(
            data=WechatInboundResponse(
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
        raw_payload=payload.raw_payload,
    )

    if payload.content_type.lower() != "text":
        inbound_log.status = "ignored"
        inbound_log.error_message = "目前仅支持文本消息"
        db.commit()
        return ApiResponse(
            data=WechatInboundResponse(
                handled=True,
                reply="目前仅支持文本消息。",
            ),
            message="目前仅支持文本消息",
        )

    identity = (
        identity_service.get_active_by_channel_user_id(payload.channel_user_id)
        or identity_service.get_active_by_conversation_id(payload.conversation_id)
    )
    if identity is None:
        inbound_log.status = "unbound"
        inbound_log.error_message = "用户未绑定"
        db.commit()
        return ApiResponse(
            data=WechatInboundResponse(
                handled=True,
                reply="你还没有绑定账号，请先在 Web 中创建二维码登录会话并完成微信确认。",
            ),
            message="用户未绑定",
        )

    user = UserService(db).get_by_id(identity.user_id)
    if user is None or user.status != "active":
        inbound_log.user_id = identity.user_id
        inbound_log.status = "failed"
        inbound_log.error_message = "账号当前不可用"
        db.commit()
        return ApiResponse(
            data=WechatInboundResponse(
                handled=True,
                reply="你的账号当前不可用，请联系系统主用户。",
            ),
            message="账号当前不可用",
        )

    inbound_log.user_id = user.id
    graph = SchedulePlanningGraph(db)
    state = graph.invoke(
        current_user=user,
        message=content,
        conversation_id=payload.conversation_id,
        channel="wechat",
    )
    inbound_log.status = "processed" if state.success else "failed"
    inbound_log.error_message = state.error
    db.commit()
    return ApiResponse(
        data=WechatInboundResponse(
            handled=True,
            reply=state.final_response or "处理完成。",
        ),
        message=state.final_response or "处理完成",
    )
