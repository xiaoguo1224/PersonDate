from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import ReminderJob, User
from app.schemas.common import ApiResponse
from app.schemas.reminder import ReminderDTO, ReminderListResponse
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _to_item(job: ReminderJob) -> ReminderDTO:
    return ReminderDTO(
        id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        title=job.title,
        conversation_id=job.conversation_id,
        trigger_time=job.trigger_time,
        status=job.status,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        error_message=job.error_message,
        fired_at=job.fired_at,
    )


@router.get("")
def list_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[ReminderListResponse]:
    service = ReminderService(db)
    jobs, total = service.list_jobs(current_user.id, status=status, page=page, page_size=page_size)
    items = [_to_item(job) for job in jobs]
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
    return ApiResponse(data=_to_item(job), message="已取消提醒")
