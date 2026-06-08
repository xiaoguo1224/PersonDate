from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import WechatAccount, WechatChannelOutboundMessage
from app.schemas.wechat_channel import (
    WechatChannelOutboundMessageItem,
    WechatChannelOutboundMessageListResponse,
    WechatGetConfigRequest,
    WechatGetConfigResponse,
    WechatGetUpdatesRequest,
    WechatGetUpdatesResponse,
    WechatGetUploadUrlRequest,
    WechatGetUploadUrlResponse,
    WechatIngestMessageRequest,
    WechatIngestMessageResponse,
    WechatSendMessageRequest,
    WechatSendTextResponse,
    WechatSendTypingRequest,
    WechatSendTypingResponse,
)
from app.services.wechat_channel_service import WechatChannelService
from wechat_channel.ilink_client import ILinkError

router = APIRouter(tags=["wechat-channel"])


def _require_channel_token(
    x_channel_token: str | None = Header(default=None, alias="X-Channel-Token"),
) -> None:
    settings = get_settings()
    if settings.wechat_channel_token and x_channel_token != settings.wechat_channel_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="微信通道令牌无效")


def _ensure_active_account(account: WechatAccount | None) -> None:
    if account is not None and account.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="微信账号当前不可用")


def _to_outbound_item(message: WechatChannelOutboundMessage) -> WechatChannelOutboundMessageItem:
    return WechatChannelOutboundMessageItem(
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


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/getupdates", response_model=WechatGetUpdatesResponse)
def get_updates(
    payload: WechatGetUpdatesRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatGetUpdatesResponse:
    service = WechatChannelService(db)
    account = service.resolve_account(account_id=payload.account_id, bot_token=payload.bot_token)
    if payload.account_id is not None or payload.bot_token is not None:
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="微信账号不存在或未绑定",
            )
        _ensure_active_account(account)
    response = service.get_updates(
        bot_token=payload.bot_token,
        account_id=payload.account_id,
        get_updates_buf=payload.get_updates_buf,
    )
    db.commit()
    return response


@router.post("/ingest", response_model=WechatIngestMessageResponse)
def ingest_message(
    payload: WechatIngestMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatIngestMessageResponse:
    service = WechatChannelService(db)
    try:
        message, deduplicated = service.ingest_message(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    db.commit()
    return WechatIngestMessageResponse(
        success=True,
        ret=0,
        account_id=message.account_id,
        message_id=message.message_id,
        cursor_token=message.cursor_token,
        status=message.status,
        deduplicated=deduplicated,
    )


@router.post("/sendmessage", response_model=WechatSendTextResponse)
def send_message(
    payload: WechatSendMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatSendTextResponse:
    service = WechatChannelService(db)
    account = None
    if payload.account_id is not None:
        account = service.get_account_by_account_id(payload.account_id)
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="微信账号不存在或未绑定",
            )
        _ensure_active_account(account)
    if account is None:
        account = service.resolve_send_account(
            conversation_id=payload.conversation_id,
            to_user_id=payload.to_user_id,
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="当前没有可用的微信账号",
            )
        _ensure_active_account(account)

    conversation_id = payload.conversation_id or payload.to_user_id
    outbound = service.create_outbound_message(
        account=account,
        to_user_id=payload.to_user_id,
        conversation_id=conversation_id,
        content=payload.content,
        context_token=payload.context_token,
        raw_payload={
            "to_user_id": payload.to_user_id,
            "conversation_id": conversation_id,
            "content": payload.content,
            "context_token": payload.context_token,
        },
    )
    db.commit()

    return WechatSendTextResponse(
        success=True,
        ret=0,
        status="queued",
        message_id=outbound.message_id,
        detail=f"消息已入队到 {conversation_id}",
    )


@router.post("/getuploadurl", response_model=WechatGetUploadUrlResponse)
def get_upload_url(
    payload: WechatGetUploadUrlRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatGetUploadUrlResponse:
    service = WechatChannelService(db)
    return service.get_upload_url(
        filekey=payload.filekey,
        media_type=payload.media_type,
        to_user_id=payload.to_user_id,
        rawsize=payload.rawsize,
        rawfilemd5=payload.rawfilemd5,
        filesize=payload.filesize,
        thumb_rawsize=payload.thumb_rawsize,
        thumb_rawfilemd5=payload.thumb_rawfilemd5,
        thumb_filesize=payload.thumb_filesize,
    )


@router.get("/outbound", response_model=WechatChannelOutboundMessageListResponse)
def list_outbound_messages(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
    account_id: str | None = Query(default=None),
    conversation_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> WechatChannelOutboundMessageListResponse:
    service = WechatChannelService(db)
    items = [
        _to_outbound_item(message)
        for message in service.list_outbound_messages(
            account_id=account_id,
            conversation_id=conversation_id,
            status=status,
            limit=limit,
        )
    ]
    return WechatChannelOutboundMessageListResponse(items=items)


@router.post("/getconfig", response_model=WechatGetConfigResponse)
def get_config(
    payload: WechatGetConfigRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatGetConfigResponse:
    service = WechatChannelService(db)
    account = service.resolve_account(account_id=payload.account_id, bot_token=payload.bot_token)
    if payload.account_id is not None or payload.bot_token is not None:
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="微信账号不存在或未绑定",
            )
        _ensure_active_account(account)
    return service.get_config(account_id=payload.account_id, bot_token=payload.bot_token)


@router.post("/sendtyping", response_model=WechatSendTypingResponse)
def send_typing(
    payload: WechatSendTypingRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> WechatSendTypingResponse:
    service = WechatChannelService(db)
    account = service.resolve_account(account_id=payload.account_id, bot_token=payload.bot_token)
    if payload.account_id is not None or payload.bot_token is not None:
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="微信账号不存在或未绑定",
            )
        _ensure_active_account(account)
    return service.send_typing(
        conversation_id=payload.conversation_id,
        typing=payload.typing,
        account_id=payload.account_id,
        bot_token=payload.bot_token,
        typing_ticket=payload.typing_ticket,
    )


@router.get("/channel/qr-code")
def generate_qr_code(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
) -> dict[str, str]:
    """生成真实的 iLink 登录二维码，返回 base64 图片数据。"""
    import base64
    from io import BytesIO

    import qrcode

    from wechat_channel.ilink_client import ILinkClient, ILinkError

    try:
        client = ILinkClient()
        result = client.get_qr_code()
    except ILinkError as exc:
        raise HTTPException(status_code=502, detail=f"获取 iLink 二维码失败: {exc.message}")

    # iLink 返回二维码 URL（如 liteapp.weixin.qq.com/...），用它生成二维码图片
    qr_data = result.qr_img_content or result.qrcode_id
    img = qrcode.make(qr_data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "qrcode_id": result.qrcode_id,
        "qr_img_content": qr_base64,
    }


@router.get("/channel/qr-code-status")
def get_qr_code_status(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[None, Depends(_require_channel_token)],
    qrcode_id: str = Query(),
) -> dict[str, object]:
    """轮询二维码扫码状态。"""
    from wechat_channel.ilink_client import ILinkClient

    try:
        client = ILinkClient()
        status = client.poll_qr_status(qrcode_id)
    except ILinkError as exc:
        raise HTTPException(status_code=502, detail=f"轮询 iLink 状态失败: {exc.message}")
    return {
        "status": status.state,
        "bot_token": status.token,
        "base_url": status.base_url,
    }
