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
    WechatIngestMessageRequest,
    WechatIngestMessageResponse,
    WechatSendMessageRequest,
    WechatSendTextResponse,
    WechatSendTypingRequest,
    WechatSendTypingResponse,
)
from app.services.wechat_channel_service import WechatChannelService

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
    return service.get_updates(
        bot_token=payload.bot_token,
        account_id=payload.account_id,
        get_updates_buf=payload.get_updates_buf,
    )


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
