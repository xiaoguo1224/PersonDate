from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_owner
from app.models import User
from app.schemas.common import ApiResponse
from app.schemas.system_setting import (
    SystemSettingItem,
    SystemSettingListResponse,
    UpdateSystemSettingsRequest,
)
from app.services.system_setting_service import SystemSettingService

router = APIRouter(prefix="/admin", tags=["system-settings"])


def _to_item(service: SystemSettingService, setting) -> SystemSettingItem:  # noqa: ANN001
    data = service.to_public_dict(setting)
    return SystemSettingItem(**data)


@router.get("/system-settings")
def list_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[SystemSettingListResponse]:
    service = SystemSettingService(db)
    items = [_to_item(service, setting) for setting in service.list_settings()]
    return ApiResponse(data=SystemSettingListResponse(items=items))


@router.patch("/system-settings")
def update_system_settings(
    payload: UpdateSystemSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[SystemSettingListResponse]:
    service = SystemSettingService(db)
    items = [_to_item(service, setting) for setting in service.update_settings(payload)]
    db.commit()
    return ApiResponse(data=SystemSettingListResponse(items=items), message="系统设置已更新")
