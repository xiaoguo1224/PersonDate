from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, MeResponse, RegisterWithInviteRequest
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(db: DbSession, payload: LoginRequest) -> ApiResponse[dict[str, str]]:
    service = AuthService(db)
    try:
        user, token = service.login(payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return ApiResponse(data={"access_token": token, "token_type": "bearer", "user_id": user.id})


@router.post("/auth/register-with-invite")
def register_with_invite(
    db: DbSession, payload: RegisterWithInviteRequest
) -> ApiResponse[dict[str, str]]:
    service = AuthService(db)
    try:
        user, token = service.register_with_invite(payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(data={"access_token": token, "token_type": "bearer", "user_id": user.id})


@router.get("/auth/me")
def me(current_user: CurrentUser, db: DbSession) -> ApiResponse[MeResponse]:
    settings = current_user.settings
    data = MeResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        email=current_user.email,
        role=current_user.role,
        status=current_user.status,
        default_timezone=settings.default_timezone if settings else None,
    )
    return ApiResponse(data=data)


@router.post("/auth/logout")
def logout(current_user: CurrentUser) -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"user_id": current_user.id}, message="已登出")
