from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReminderJob, ReminderStatus
from app.services.channel_identity_service import ChannelIdentityService
from app.services.wechat_channel_service import WechatChannelService


class ReminderWorker:
    def __init__(self, db: Session, sender: object | None = None) -> None:
        self.db = db
        self.wechat = WechatChannelService(db, sender=sender)
        self.channel_identities = ChannelIdentityService(db)

    def run_once(self, now: datetime | None = None) -> list[ReminderJob]:
        current_time = now or datetime.now(UTC)
        stmt = select(ReminderJob).where(
            ReminderJob.status == ReminderStatus.PENDING.value,
            ReminderJob.trigger_time <= current_time,
        )
        jobs = list(self.db.scalars(stmt.order_by(ReminderJob.trigger_time.asc())))
        for job in jobs:
            # 发送时通过 user_id 实时查询当前活跃的 conversation_id
            conversation_id = self.channel_identities.get_conversation_id(job.user_id)
            log = self.wechat.send_text(
                conversation_id=conversation_id,
                content=f"提醒：{job.title}即将开始。",
                user_id=job.user_id,
            )
            if log.status == "sent":
                job.status = ReminderStatus.FIRED.value
                job.fired_at = current_time
                job.error_message = None
                continue

            job.retry_count += 1
            job.error_message = log.error_message
            if job.retry_count >= job.max_retries:
                job.status = ReminderStatus.FAILED.value
        self.db.commit()
        return jobs
