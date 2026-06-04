from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.schemas.reminder import ReminderDTO, ReminderListResponse
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _to_item(job) -> ReminderDTO:
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
    )


@router.get("")
def list_reminders(
    db: DbSession, current_user: CurrentUser, status: str | None = None
) -> ApiResponse[ReminderListResponse]:
    items = [_to_item(job) for job in ReminderService(db).list_jobs(current_user.id, status)]
    return ApiResponse(data=ReminderListResponse(items=items))


@router.patch("/{reminder_id}/cancel")
def cancel_reminder(
    db: DbSession, current_user: CurrentUser, reminder_id: str
) -> ApiResponse[ReminderDTO]:
    service = ReminderService(db)
    job = service.get_job(current_user.id, reminder_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    service.cancel_job(job)
    db.commit()
    return ApiResponse(data=_to_item(job), message="已取消提醒")
