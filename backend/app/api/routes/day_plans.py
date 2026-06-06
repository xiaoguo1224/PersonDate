from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import DayPlan, PlanItem, User
from app.schemas.common import ApiResponse
from app.schemas.plan import DayPlanConfirmResponse, DayPlanDTO, DayPlanGenerateRequest, PlanItemDTO
from app.services.day_plan_service import DayPlanService

router = APIRouter(prefix="/day-plans", tags=["day-plans"])


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


def _to_day_plan(plan: DayPlan) -> DayPlanDTO:
    return DayPlanDTO(
        id=plan.id,
        plan_date=plan.plan_date,
        summary=plan.summary,
        status=plan.status,
        items=[_to_item(item) for item in plan.items],
    )


@router.get("/{plan_date}")
def get_day_plan(
    plan_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DayPlanDTO | None]:
    plan = DayPlanService(db).list_day_plan(current_user.id, plan_date)
    return ApiResponse(data=_to_day_plan(plan) if plan else None)


@router.post("/{plan_date}/generate")
def generate_day_plan(
    plan_date: date,
    payload: DayPlanGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DayPlanDTO]:
    service = DayPlanService(db)
    plan = service.generate_draft(current_user.id, plan_date)
    db.commit()
    return ApiResponse(data=_to_day_plan(plan), message="安排草案已生成")


@router.post("/{plan_id}/confirm")
def confirm_day_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DayPlanConfirmResponse]:
    service = DayPlanService(db)
    plan = service.get_day_plan(current_user.id, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    service.confirm_plan(plan)
    db.commit()
    return ApiResponse(
        data=DayPlanConfirmResponse(id=plan.id, plan_date=plan.plan_date, status=plan.status),
        message="安排已确认",
    )
