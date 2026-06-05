from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_owner
from app.models import ChannelIdentity, ChannelMessageLog, User
from app.schemas.common import ApiResponse
from app.schemas.wechat import (
    ChannelIdentityItem,
    ChannelIdentityListResponse,
    ChannelMessageLogItem,
    ChannelMessageLogListResponse,
    WechatBindingCodeResponse,
    WechatStatusResponse,
)
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


@router.post("/me/wechat-binding-code")
def create_wechat_binding_code(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[WechatBindingCodeResponse]:
    service = WechatChannelService(db)
    binding_code = service.generate_binding_code(current_user.id)
    db.commit()
    return ApiResponse(
        data=WechatBindingCodeResponse(code=binding_code.code, expires_at=binding_code.expires_at),
        message=f"请在微信中发送：绑定 {binding_code.code}",
    )


@router.get("/me/channel-identities")
def list_my_channel_identities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ChannelIdentityListResponse]:
    service = WechatChannelService(db)
    items = [_to_identity_item(identity) for identity in service.list_identities(current_user.id)]
    return ApiResponse(data=ChannelIdentityListResponse(items=items))


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
    conversation_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> ApiResponse[ChannelMessageLogListResponse]:
    service = WechatChannelService(db)
    items = [
        _to_message_log_item(log)
        for log in service.list_message_logs(
            user_id=current_user.id,
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
    conversation_id: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> ApiResponse[ChannelMessageLogListResponse]:
    service = WechatChannelService(db)
    items = [
        _to_message_log_item(log)
        for log in service.list_message_logs(
            conversation_id=conversation_id,
            direction=direction,
            limit=limit,
        )
    ]
    return ApiResponse(data=ChannelMessageLogListResponse(items=items))
