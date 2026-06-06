from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import PlanItem, User
from app.schemas.common import ApiResponse
from app.schemas.plan import (
    PlanItemCreateRequest,
    PlanItemDTO,
    PlanItemUpdateRequest,
)
from app.services.plan_item_service import PlanItemService

router = APIRouter(prefix="/plan-items", tags=["plan-items"])


def _to_item(item: PlanItem) -> PlanItemDTO:
    return PlanItemDTO(
        id=item.id,
        day_plan_id=item.day_plan_id,
        title=item.title,
        item_type=item.item_type,
        start_time=item.start_time,
        end_time=item.end_time,
        status=item.status,
        is_flexible=item.is_flexible,
        sort_order=item.sort_order,
        ref_id=item.ref_id,
    )


@router.post("")
def create_plan_item(
    payload: PlanItemCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PlanItemDTO]:
    service = PlanItemService(db)
    item = service.create_plan_item(
        user_id=current_user.id,
        plan_date=payload.plan_date,
        title=payload.title,
        item_type=payload.item_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status,
        is_flexible=payload.is_flexible,
        sort_order=payload.sort_order,
        ref_id=payload.ref_id,
    )
    db.commit()
    return ApiResponse(data=_to_item(item), message="安排项已创建")


@router.patch("/{plan_item_id}")
def update_plan_item(
    plan_item_id: str,
    payload: PlanItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PlanItemDTO]:
    service = PlanItemService(db)
    item = service.get_plan_item(current_user.id, plan_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排项不存在")
    item = service.update_plan_item(
        item,
        title=payload.title,
        item_type=payload.item_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status,
        is_flexible=payload.is_flexible,
        sort_order=payload.sort_order,
        ref_id=payload.ref_id,
    )
    db.commit()
    return ApiResponse(data=_to_item(item), message="安排项已更新")


@router.patch("/{plan_item_id}/complete")
def complete_plan_item(
    plan_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PlanItemDTO]:
    service = PlanItemService(db)
    item = service.get_plan_item(current_user.id, plan_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排项不存在")
    item = service.complete_plan_item(item)
    db.commit()
    return ApiResponse(data=_to_item(item), message="安排项已完成")


@router.delete("/{plan_item_id}")
def delete_plan_item(
    plan_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[PlanItemDTO]:
    service = PlanItemService(db)
    item = service.get_plan_item(current_user.id, plan_item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排项不存在")
    item = service.delete_plan_item(item)
    db.commit()
    return ApiResponse(data=_to_item(item), message="安排项已删除")
