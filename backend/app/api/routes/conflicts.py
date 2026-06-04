from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import ScheduleConflict, User
from app.schemas.common import ApiResponse
from app.schemas.conflict import ConflictDTO, ConflictListResponse
from app.services.conflict_service import ConflictService

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


def _to_item(conflict: ScheduleConflict) -> ConflictDTO:
    return ConflictDTO(
        id=conflict.id,
        conflict_type=conflict.conflict_type,
        severity=conflict.severity,
        title=conflict.title,
        description=conflict.description,
        related_item_ids=conflict.related_item_ids,
        suggestion=conflict.suggestion,
        status=conflict.status,
        detected_at=conflict.detected_at,
    )


@router.get("")
def list_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str | None = None,
) -> ApiResponse[ConflictListResponse]:
    items = [_to_item(item) for item in ConflictService(db).list_conflicts(current_user.id, status)]
    return ApiResponse(data=ConflictListResponse(items=items))


@router.post("/detect")
def detect_conflicts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: str | None = None,
) -> ApiResponse[ConflictListResponse]:
    service = ConflictService(db)
    items = [_to_item(item) for item in service.detect_day_conflicts(current_user.id)]
    db.commit()
    return ApiResponse(data=ConflictListResponse(items=items), message="已完成冲突检测")


@router.patch("/{conflict_id}/ignore")
def ignore_conflict(
    conflict_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ConflictDTO]:
    service = ConflictService(db)
    conflict = service.get_conflict(current_user.id, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="冲突不存在")
    service.ignore_conflict(conflict)
    db.commit()
    return ApiResponse(data=_to_item(conflict), message="已忽略冲突")


@router.patch("/{conflict_id}/resolve")
def resolve_conflict(
    conflict_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ConflictDTO]:
    service = ConflictService(db)
    conflict = service.get_conflict(current_user.id, conflict_id)
    if conflict is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="冲突不存在")
    service.resolve_conflict(conflict)
    db.commit()
    return ApiResponse(data=_to_item(conflict), message="已标记解决")
