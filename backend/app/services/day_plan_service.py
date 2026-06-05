from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DayPlan,
    DayPlanStatus,
    PlanItem,
    PlanItemStatus,
    PlanItemType,
    TaskItem,
    TaskStatus,
)
from app.services.conflict_service import ConflictService


class DayPlanService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.conflicts = ConflictService(db)

    def get_or_create_draft(
        self, user_id: str, plan_date: date, summary: str | None = None
    ) -> DayPlan:
        stmt = select(DayPlan).where(
            DayPlan.user_id == user_id,
            DayPlan.plan_date == plan_date,
            DayPlan.status == DayPlanStatus.DRAFT.value,
        )
        draft = self.db.scalar(stmt)
        if draft is not None:
            return draft
        draft = DayPlan(
            user_id=user_id, plan_date=plan_date, summary=summary, status=DayPlanStatus.DRAFT.value
        )
        self.db.add(draft)
        self.db.flush()
        return draft

    def get_or_create_day_plan(
        self,
        user_id: str,
        plan_date: date,
        summary: str | None = None,
    ) -> DayPlan:
        plan = self.list_day_plan(user_id, plan_date)
        if plan is not None:
            return plan
        return self.get_or_create_draft(user_id, plan_date, summary=summary)

    def generate_draft(self, user_id: str, plan_date: date) -> DayPlan:
        draft = self.get_or_create_draft(
            user_id, plan_date, summary=f"{plan_date.isoformat()} 的草案"
        )
        if draft.items:
            return draft

        day_start = datetime.combine(plan_date, time(9, 0), tzinfo=UTC)
        cursor = day_start
        tasks = list(
            self.db.scalars(
                select(TaskItem)
                .where(
                    TaskItem.user_id == user_id,
                    TaskItem.status == TaskStatus.PENDING.value,
                )
                .order_by(TaskItem.created_at.asc())
            )
        )
        for task in tasks:
            minutes = task.estimated_minutes or 60
            start_time = cursor
            end_time = cursor + timedelta(minutes=minutes)
            item = PlanItem(
                day_plan_id=draft.id,
                user_id=user_id,
                item_type=PlanItemType.TASK.value,
                ref_id=task.id,
                title=task.title,
                start_time=start_time,
                end_time=end_time,
                status=PlanItemStatus.PLANNED.value,
                is_flexible=True,
            )
            self.db.add(item)
            cursor = end_time + timedelta(minutes=15)

        self.conflicts.detect_day_conflicts(user_id)
        return draft

    def confirm_plan(self, day_plan: DayPlan) -> DayPlan:
        stmt = select(DayPlan).where(
            DayPlan.user_id == day_plan.user_id,
            DayPlan.plan_date == day_plan.plan_date,
            DayPlan.id != day_plan.id,
            DayPlan.status.in_(
                [
                    DayPlanStatus.DRAFT.value,
                    DayPlanStatus.CONFIRMED.value,
                    DayPlanStatus.ACTIVE.value,
                ]
            ),
        )
        for other_plan in self.db.scalars(stmt):
            other_plan.status = DayPlanStatus.DELETED.value
        self.db.flush()
        day_plan.status = DayPlanStatus.CONFIRMED.value
        self.db.flush()
        for item in day_plan.items:
            item.status = PlanItemStatus.PLANNED.value
        return day_plan

    def list_day_plan(self, user_id: str, plan_date: date) -> DayPlan | None:
        stmt = (
            select(DayPlan)
            .where(
                DayPlan.user_id == user_id,
                DayPlan.plan_date == plan_date,
                DayPlan.status != DayPlanStatus.DELETED.value,
            )
            .order_by(DayPlan.created_at.desc())
        )
        return self.db.scalar(stmt)

    def get_day_plan(self, user_id: str, plan_id: str) -> DayPlan | None:
        stmt = select(DayPlan).where(DayPlan.user_id == user_id, DayPlan.id == plan_id)
        return self.db.scalar(stmt)
