from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.cache_invalidator import invalidate_user_reminders
from app.models import ReminderJob, ReminderStatus, ScheduledItem, User
from app.schemas.common import ApiResponse
from app.schemas.reminder import ReminderDTO, ReminderListResponse
from app.services.reminder_service import ReminderService


class ReactivateRequest(BaseModel):
    trigger_time: datetime | None = None


class AdjustRemindBeforeRequest(BaseModel):
    remind_before_minutes: int = Field(ge=0, le=1440)


router = APIRouter(prefix="/reminders", tags=["reminders"])


def _to_item(job: ReminderJob, scheduled_item: ScheduledItem | None = None) -> ReminderDTO:
    original_time = None
    remind_before = 0
    source_task_id = None
    if scheduled_item is not None:
        original_time = scheduled_item.start_time
        remind_before = scheduled_item.remind_before_minutes or 0
        source_task_id = scheduled_item.source_task_id
    return ReminderDTO(
        id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        source_task_id=source_task_id,
        title=job.title,
        conversation_id=job.conversation_id,
        original_time=original_time,
        trigger_time=job.trigger_time,
        remind_before_minutes=remind_before,
        status=job.status,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        error_message=job.error_message,
        fired_at=job.fired_at,
    )


def _load_scheduled_items_map(
    db: Session, jobs: list[ReminderJob]
) -> dict[str, ScheduledItem]:
    target_ids = [
        j.target_id for j in jobs if j.target_type == "scheduled_item"
    ]
    if not target_ids:
        return {}
    stmt = select(ScheduledItem).where(ScheduledItem.id.in_(target_ids))
    items = db.scalars(stmt).all()
    return {item.id: item for item in items}


@router.get("")
def list_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str | None = None,
    keyword: str | None = None,
    sort_order: Literal["trigger_time_asc", "trigger_time_desc"] = Query(default="trigger_time_asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[ReminderListResponse]:
    service = ReminderService(db)
    jobs, total = service.list_jobs(
        current_user.id,
        status=status,
        keyword=keyword,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    item_map = _load_scheduled_items_map(db, jobs)
    items = [_to_item(job, item_map.get(job.target_id)) for job in jobs]
    return ApiResponse(data=ReminderListResponse(items=items, total=total, page=page, page_size=page_size))


@router.patch("/{reminder_id}/cancel")
def cancel_reminder(
    reminder_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ReminderDTO]:
    service = ReminderService(db)
    job = service.get_job(current_user.id, reminder_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    service.cancel_job(job)
    db.commit()
    scheduled_item = db.get(ScheduledItem, job.target_id) if job.target_type == "scheduled_item" else None
    return ApiResponse(data=_to_item(job, scheduled_item), message="已取消提醒")


@router.patch("/{reminder_id}/reactivate")
def reactivate_reminder(
    reminder_id: str,
    payload: ReactivateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ReminderDTO]:
    service = ReminderService(db)
    job = service.get_job(current_user.id, reminder_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")

    now = datetime.now(UTC)
    new_trigger_time = payload.trigger_time if payload else None

    if job.trigger_time <= now and not new_trigger_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="提醒已过期，请提供新的触发时间"
        )

    service.reactivate_job(job, new_trigger_time)
    db.commit()
    scheduled_item = db.get(ScheduledItem, job.target_id) if job.target_type == "scheduled_item" else None
    return ApiResponse(data=_to_item(job, scheduled_item), message="已重新激活提醒")


@router.patch("/{reminder_id}/adjust")
def adjust_remind_before(
    reminder_id: str,
    payload: AdjustRemindBeforeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ReminderDTO]:
    service = ReminderService(db)
    job = service.get_job(current_user.id, reminder_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    if job.status != ReminderStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能调整待触发状态的提醒",
        )

    scheduled_item = None
    if job.target_type == "scheduled_item":
        scheduled_item = db.get(ScheduledItem, job.target_id)

    if scheduled_item is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该提醒不支持调整提前时间",
        )

    new_remind_before = payload.remind_before_minutes
    scheduled_item.remind_before_minutes = new_remind_before
    job.trigger_time = scheduled_item.start_time - timedelta(minutes=new_remind_before)

    now = datetime.now(UTC)
    if job.trigger_time <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="调整后的触发时间已过期，请减少提前分钟数",
        )

    invalidate_user_reminders(current_user.id)
    db.commit()
    return ApiResponse(data=_to_item(job, scheduled_item), message="已调整提醒时间")
