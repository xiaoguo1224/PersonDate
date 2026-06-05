from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PlanItem, PlanItemStatus
from app.services.day_plan_service import DayPlanService


class PlanItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.day_plans = DayPlanService(db)

    def create_plan_item(
        self,
        *,
        user_id: str,
        plan_date: date,
        title: str,
        item_type: str,
        start_time: datetime,
        end_time: datetime,
        status: str,
        is_flexible: bool,
        sort_order: int | None,
        ref_id: str | None,
    ) -> PlanItem:
        day_plan = self.day_plans.get_or_create_day_plan(
            user_id,
            plan_date,
            summary=f"{plan_date.isoformat()} 的草案",
        )
        item = PlanItem(
            day_plan_id=day_plan.id,
            user_id=user_id,
            item_type=item_type,
            ref_id=ref_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            status=status,
            is_flexible=is_flexible,
            sort_order=sort_order,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def get_plan_item(self, user_id: str, plan_item_id: str) -> PlanItem | None:
        stmt = select(PlanItem).where(PlanItem.user_id == user_id, PlanItem.id == plan_item_id)
        return self.db.scalar(stmt)

    def update_plan_item(self, item: PlanItem, **changes: object) -> PlanItem:
        for key, value in changes.items():
            if value is not None:
                setattr(item, key, value)
        return item

    def complete_plan_item(self, item: PlanItem) -> PlanItem:
        item.status = PlanItemStatus.COMPLETED.value
        return item

    def delete_plan_item(self, item: PlanItem) -> PlanItem:
        item.status = PlanItemStatus.CANCELLED.value
        return item
