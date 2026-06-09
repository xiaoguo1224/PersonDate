import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_reminders
from app.models import ReminderJob, ReminderStatus
from app.models.enums import ReminderTargetType

logger = logging.getLogger(__name__)

_REMINDERS_TTL = 600  # 10 分钟


class ReminderService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_for_target(
        self,
        *,
        user_id: str,
        target_type: str,
        target_id: str,
        title: str,
        trigger_time: datetime,
    ) -> ReminderJob:
        job = ReminderJob(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            title=title,
            trigger_time=trigger_time,
            status=ReminderStatus.PENDING.value,
        )
        self.db.add(job)
        self.db.flush()
        invalidate_user_reminders(user_id)
        logger.info("创建提醒 user_id=%s target_type=%s target_id=%s trigger=%s", user_id, target_type, target_id, trigger_time.isoformat())
        return job

    def create_from_scheduled_item(
        self,
        user_id: str,
        scheduled_item_id: str,
        title: str,
        trigger_time: datetime,
        remind_before_minutes: int,
    ) -> ReminderJob:
        actual_trigger = trigger_time - timedelta(minutes=remind_before_minutes)
        reminder = ReminderJob(
            user_id=user_id,
            target_type=ReminderTargetType.SCHEDULED_ITEM.value,
            target_id=scheduled_item_id,
            title=title,
            trigger_time=actual_trigger,
            status=ReminderStatus.PENDING.value,
        )
        self.db.add(reminder)
        self.db.flush()
        invalidate_user_reminders(user_id)
        logger.info("创建日程提醒 user_id=%s item_id=%s trigger=%s", user_id, scheduled_item_id, actual_trigger.isoformat())
        return reminder

    def cancel_by_target(self, *, user_id: str, target_id: str) -> None:
        logger.info("取消目标提醒 user_id=%s target_id=%s", user_id, target_id)
        stmt = select(ReminderJob).where(
            ReminderJob.user_id == user_id,
            ReminderJob.target_id == target_id,
            ReminderJob.status == ReminderStatus.PENDING.value,
        )
        for job in self.db.scalars(stmt):
            job.status = ReminderStatus.CANCELED.value
        invalidate_user_reminders(user_id)

    def list_jobs(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReminderJob], int]:
        base = select(ReminderJob).where(ReminderJob.user_id == user_id)
        if status:
            base = base.where(ReminderJob.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            base = base.where(ReminderJob.title.ilike(pattern))
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        items = list(
            self.db.scalars(
                base.order_by(ReminderJob.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def get_job(self, user_id: str, job_id: str) -> ReminderJob | None:
        stmt = select(ReminderJob).where(ReminderJob.user_id == user_id, ReminderJob.id == job_id)
        return self.db.scalar(stmt)

    def list_jobs_cached(self, user_id: str, status: str | None = None) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:reminders:status:{status or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items, _ = self.list_jobs(user_id, status=status, page_size=100)
        result = [
            {
                "id": item.id,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "title": item.title,
                "trigger_time": item.trigger_time.isoformat(),
                "status": item.status,
                "retry_count": item.retry_count,
                "max_retries": item.max_retries,
                "error_message": item.error_message,
                "fired_at": item.fired_at.isoformat() if item.fired_at else None,
                "conversation_id": item.conversation_id,
            }
            for item in items
        ]
        cache_set(cache_key, result, _REMINDERS_TTL)
        return result

    def cancel_job(self, job: ReminderJob) -> ReminderJob:
        job.status = ReminderStatus.CANCELED.value
        invalidate_user_reminders(job.user_id)
        logger.info("取消提醒 job_id=%s user_id=%s", job.id, job.user_id)
        return job

    def reactivate_job(self, job: ReminderJob, new_trigger_time: datetime | None = None) -> ReminderJob:
        job.status = ReminderStatus.PENDING.value
        job.retry_count = 0
        job.error_message = None
        if new_trigger_time:
            job.trigger_time = new_trigger_time
        return job

    def fire_due_jobs(self, now: datetime | None = None) -> list[ReminderJob]:
        now = now or datetime.now(UTC)
        stmt = select(ReminderJob).where(
            ReminderJob.status == ReminderStatus.PENDING.value,
            ReminderJob.trigger_time <= now,
        )
        jobs = list(self.db.scalars(stmt))
        fired_user_ids: set[str] = set()
        for job in jobs:
            job.status = ReminderStatus.FIRED.value
            job.fired_at = now
            fired_user_ids.add(job.user_id)
        for uid in fired_user_ids:
            invalidate_user_reminders(uid)
        logger.info("触发到期提醒 count=%d", len(jobs))
        return jobs
