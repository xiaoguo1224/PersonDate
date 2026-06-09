from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.user_settings import UpdateUserSettingsRequest, UserSettingsResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/me", tags=["me"])


def _to_settings_response(settings: Any) -> UserSettingsResponse:
    return UserSettingsResponse(
        default_timezone=settings.default_timezone,
        workday_start_time=settings.workday_start_time,
        workday_end_time=settings.workday_end_time,
        daily_plan_push_time=settings.daily_plan_push_time,
        default_remind_before_minutes=settings.default_remind_before_minutes,
        daily_plan_push_enabled=settings.daily_plan_push_enabled,
        city=settings.city,
    )


@router.get("/settings")
def get_my_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserSettingsResponse]:
    settings = UserService(db).ensure_settings(current_user.id)
    return ApiResponse(data=_to_settings_response(settings))


@router.patch("/settings")
def update_my_settings(
    payload: UpdateUserSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserSettingsResponse]:
    service = UserService(db)
    settings = service.update_settings(current_user.id, payload)
    db.commit()
    return ApiResponse(data=_to_settings_response(settings), message="设置已更新")
