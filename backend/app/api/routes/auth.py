from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_refresh_user
from app.core.security import clear_auth_cookie, create_access_token, set_auth_cookie
from app.models import User
from app.schemas.auth import LoginRequest, MeResponse, RegisterWithInviteRequest
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/auth/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, str]]:
    service = AuthService(db)
    try:
        user, access_token, refresh_token = service.login(payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    set_auth_cookie(response, refresh_token)
    return ApiResponse(
        data={"access_token": access_token, "token_type": "bearer", "user_id": user.id}
    )


@router.post("/auth/register-with-invite")
def register_with_invite(
    payload: RegisterWithInviteRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, str]]:
    service = AuthService(db)
    try:
        user, access_token, refresh_token = service.register_with_invite(payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    set_auth_cookie(response, refresh_token)
    return ApiResponse(
        data={"access_token": access_token, "token_type": "bearer", "user_id": user.id}
    )


@router.get("/auth/me")
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[MeResponse]:
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


@router.post("/auth/refresh")
def refresh(
    current_user: User = Depends(get_refresh_user),
) -> ApiResponse[dict[str, str]]:
    access_token = create_access_token(
        subject=current_user.id,
        claims={
            "user_id": current_user.id,
            "role": current_user.role,
            "username": current_user.username,
        },
    )
    return ApiResponse(
        data={"access_token": access_token, "token_type": "bearer", "user_id": current_user.id}
    )


@router.post("/auth/logout")
def logout(response: Response) -> ApiResponse[dict[str, str]]:
    clear_auth_cookie(response)
    return ApiResponse(data={}, message="已登出")
