from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_owner
from app.models import ChannelIdentity, User, UserRole, UserStatus
from app.schemas.common import ApiResponse
from app.schemas.user import (
    ChannelIdentityAdminItem,
    ChannelIdentityAdminListResponse,
    UserAdminItem,
    UserAdminListResponse,
)
from app.services.channel_identity_service import ChannelIdentityService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["users"])


def _to_user_item(user: User) -> UserAdminItem:
    settings = user.settings
    return UserAdminItem(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        status=user.status,
        default_timezone=settings.default_timezone if settings else None,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _to_identity_item(identity: ChannelIdentity) -> ChannelIdentityAdminItem:
    return ChannelIdentityAdminItem(
        id=identity.id,
        channel=identity.channel,
        channel_user_id=identity.channel_user_id,
        conversation_id=identity.conversation_id,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
        status=identity.status,
        bound_at=identity.bound_at,
        created_at=identity.created_at,
    )


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[UserAdminListResponse]:
    items = [_to_user_item(user) for user in UserService(db).list_users()]
    return ApiResponse(data=UserAdminListResponse(items=items))


@router.patch("/users/{user_id}/disable")
def disable_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[UserAdminItem]:
    service = UserService(db)
    user = service.get_by_id(user_id)
    if user is None or user.status == UserStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.role == UserRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用 owner 用户")
    service.disable_user(user)
    db.commit()
    return ApiResponse(data=_to_user_item(user), message="已禁用用户")


@router.patch("/users/{user_id}/enable")
def enable_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[UserAdminItem]:
    service = UserService(db)
    user = service.get_by_id(user_id)
    if user is None or user.status == UserStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.role == UserRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改 owner 用户状态",
        )
    service.enable_user(user)
    db.commit()
    return ApiResponse(data=_to_user_item(user), message="已启用用户")


@router.get("/users/{user_id}/channel-identities")
def list_user_channel_identities(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[ChannelIdentityAdminListResponse]:
    service = UserService(db)
    user = service.get_by_id(user_id)
    if user is None or user.status == UserStatus.DELETED.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    identities = ChannelIdentityService(db).list_identities(user_id)
    items = [_to_identity_item(identity) for identity in identities]
    return ApiResponse(data=ChannelIdentityAdminListResponse(items=items))
