from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, OwnerUser
from app.schemas.common import ApiResponse
from app.schemas.invite_code import InviteCodeCreateRequest, InviteCodeItem, InviteCodeListResponse
from app.services.invite_code_service import InviteCodeService

router = APIRouter(prefix="/admin", tags=["invite-codes"])


@router.post("/invite-codes")
def create_invite_code(
    db: DbSession, current_user: OwnerUser, payload: InviteCodeCreateRequest
) -> ApiResponse[InviteCodeItem]:
    service = InviteCodeService(db)
    invite_code = service.create(current_user, payload)
    db.commit()
    return ApiResponse(
        data=InviteCodeItem(
            id=invite_code.id,
            code=invite_code.code,
            max_uses=invite_code.max_uses,
            used_count=invite_code.used_count,
            expires_at=invite_code.expires_at,
            status=invite_code.status,
            remark=invite_code.remark,
        )
    )


@router.get("/invite-codes")
def list_invite_codes(
    db: DbSession, current_user: OwnerUser
) -> ApiResponse[InviteCodeListResponse]:
    service = InviteCodeService(db)
    items = [
        InviteCodeItem(
            id=item.id,
            code=item.code,
            max_uses=item.max_uses,
            used_count=item.used_count,
            expires_at=item.expires_at,
            status=item.status,
            remark=item.remark,
        )
        for item in service.list_all()
    ]
    return ApiResponse(data=InviteCodeListResponse(items=items))


@router.patch("/invite-codes/{invite_code_id}/disable")
def disable_invite_code(
    db: DbSession, current_user: OwnerUser, invite_code_id: str
) -> ApiResponse[dict[str, str]]:
    from app.models import InviteCode

    invite_code = db.get(InviteCode, invite_code_id)
    if invite_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请码不存在")

    service = InviteCodeService(db)
    service.disable(invite_code)
    db.commit()
    return ApiResponse(data={"id": invite_code.id}, message="已禁用邀请码")
