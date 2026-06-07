import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph
from app.api.deps import get_current_user, get_db, require_owner
from app.core.wechat_channel import build_wechat_channel_client
from app.models import (
    ChannelIdentity,
    ChannelMessageLog,
    User,
    WechatAccount,
    WechatChannelOutboundMessage,
    WechatLoginSession,
)
from app.schemas.common import ApiResponse
from app.schemas.wechat import (
    ChannelIdentityItem,
    ChannelIdentityListResponse,
    ChannelMessageLogItem,
    ChannelMessageLogListResponse,
    NotificationSettingsUpdateRequest,
    WechatAccountItem,
    WechatAccountListResponse,
    WechatInboundRequest,
    WechatInboundResponse,
    WechatLoginSessionConfirmRequest,
    WechatLoginSessionCreateResponse,
    WechatLoginSessionItem,
    WechatOutboundQueueItem,
    WechatOutboundQueueListResponse,
    WechatSendTextRequest,
    WechatSendTextResponse,
    WechatStatusResponse,
)
from app.services.wechat_channel_adapter import WechatChannelAdapter
from app.services.wechat_channel_service import WechatChannelService

logger = logging.getLogger(__name__)

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
        context_token=log.context_token,
        raw_payload=log.raw_payload,
        status=log.status,
        retry_count=log.retry_count,
        error_code=log.error_code,
        error_message=log.error_message,
        created_at=log.created_at,
    )


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


def _to_outbound_queue_item(message: WechatChannelOutboundMessage) -> WechatOutboundQueueItem:
    return WechatOutboundQueueItem(
        id=message.id,
        account_id=message.account_id,
        message_id=message.message_id,
        to_user_id=message.to_user_id,
        conversation_id=message.conversation_id,
        content=message.content,
        context_token=message.context_token,
        raw_payload=message.raw_payload,
        status=message.status,
        retry_count=message.retry_count,
        error_code=message.error_code,
        error_message=message.error_message,
        sent_at=message.sent_at,
        created_at=message.created_at,
        updated_at=message.updated_at,
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

    # 调 wechat-channel 获取真实二维码
    channel_client = build_wechat_channel_client()
    if channel_client is None:
        raise HTTPException(status_code=503, detail="微信通道服务不可用")
    try:
        qr = channel_client.get_channel_qr_code()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"获取二维码失败: {exc}")

    # 创建 session，写入真实二维码数据
    session = service.create_login_session(current_user.id)
    session.qr_img_content = qr["qr_img_content"]
    session.qrcode_id = qr["qrcode_id"]
    db.commit()

    return ApiResponse(
        data=WechatLoginSessionCreateResponse(
            login_session_id=session.login_session_id,
            qr_payload=session.qr_payload,
            qr_img_content=session.qr_img_content,
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

    # 如果已有真实二维码且未确认，轮询 iLink 扫码状态
    if session.qrcode_id and session.status in ("qr_created", "scanned"):
        channel_client = build_wechat_channel_client()
        if channel_client is not None:
            try:
                status = channel_client.get_channel_qr_code_status(session.qrcode_id)
                remote_state = status["status"]
                if remote_state == "scanned":
                    session.status = "scanned"
                    db.commit()
                elif remote_state == "confirmed":
                    bot_token = status["bot_token"]
                    base_url = status["base_url"]
                    wechat_user_id = status.get("wechat_user_id") or session.qrcode_id
                    service.confirm_login_session(
                        owner_user_id=current_user.id,
                        login_session_id=login_session_id,
                        account_id=session.qrcode_id,
                        wechat_user_id=wechat_user_id,
                        bot_token=bot_token,
                        base_url=base_url,
                    )
                    db.commit()
                elif remote_state == "expired":
                    session.status = "expired"
                    db.commit()
            except Exception:
                logger.warning("轮询二维码状态失败: session=%s qrcode_id=%s", session.id, session.qrcode_id, exc_info=True)

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
            queued_outbound_messages=summary["queued_outbound_messages"],
            sent_outbound_messages=summary["sent_outbound_messages"],
            failed_outbound_messages=summary["failed_outbound_messages"],
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


@router.get("/admin/wechat/outbound-queue")
def list_admin_wechat_outbound_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
    account_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> ApiResponse[WechatOutboundQueueListResponse]:
    service = WechatChannelService(db)
    items = [
        _to_outbound_queue_item(message)
        for message in service.list_outbound_messages(
            account_id=account_id,
            conversation_id=conversation_id,
            status=status,
            limit=limit,
        )
    ]
    return ApiResponse(data=WechatOutboundQueueListResponse(items=items))


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
            sent=log.status in {"queued", "sent"},
            conversation_id=log.conversation_id,
            content=log.content or payload.content,
            message_id=log.message_id,
            status=log.status,
            error_message=log.error_message,
        ),
        message=(
            "测试消息已发送"
            if log.status == "sent"
            else "测试消息已入队"
            if log.status == "queued"
            else "测试消息发送失败"
        ),
    )


@router.get("/me/notification-settings")
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    from app.models.user import UserSettings

    settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    if settings is None:
        return ApiResponse(data={
            "daily_plan_push_enabled": False,
            "daily_plan_push_time": "08:00",
            "city": None,
        })
    return ApiResponse(data={
        "daily_plan_push_enabled": settings.daily_plan_push_enabled,
        "daily_plan_push_time": settings.daily_plan_push_time,
        "city": settings.city,
    })


@router.put("/me/notification-settings")
def update_notification_settings(
    payload: NotificationSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    from app.models.user import UserSettings

    settings = db.scalar(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    if settings is None:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        db.flush()
    settings.daily_plan_push_enabled = payload.daily_plan_push_enabled
    settings.daily_plan_push_time = payload.daily_plan_push_time
    settings.city = payload.city
    db.commit()
    return ApiResponse(message="已保存")


@router.post("/wechat/inbound")
def inbound_wechat_message(
    payload: WechatInboundRequest,
    db: Session = Depends(get_db),
    channel_token: str | None = Header(default=None, alias="X-Channel-Token"),
) -> ApiResponse[WechatInboundResponse]:
    adapter = WechatChannelAdapter(db, graph_cls=SchedulePlanningGraph)
    result = adapter.handle_inbound_message(payload, channel_token)
    return ApiResponse(
        data=result.response,
        message=result.message,
    )
