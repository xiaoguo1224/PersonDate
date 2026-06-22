from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReminderJob, ReminderStatus, ScheduledItem, UserSettings
from app.models.enums import ReminderTargetType
from app.services.channel_identity_service import ChannelIdentityService
from app.services.wechat_channel_service import WechatChannelService

logger = logging.getLogger(__name__)


class ReminderWorker:
    def __init__(self, db: Session, sender: object | None = None) -> None:
        self.db = db
        self.wechat = WechatChannelService(db, sender=sender)
        self.channel_identities = ChannelIdentityService(db)

    def _build_message(self, job: ReminderJob) -> str:
        if job.target_type != ReminderTargetType.SCHEDULED_ITEM.value:
            return f"提醒：{job.title}即将开始。"

        item = self.db.get(ScheduledItem, job.target_id)
        if not item:
            return f"提醒：{job.title}即将开始。"

        tz_name = "Asia/Shanghai"
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == job.user_id))
        if settings:
            tz_name = settings.default_timezone
        try:
            local_tz = ZoneInfo(tz_name)
        except Exception:
            local_tz = ZoneInfo("Asia/Shanghai")

        start_str = item.start_time.astimezone(local_tz).strftime("%H:%M")
        end_str = item.end_time.astimezone(local_tz).strftime("%H:%M")
        date_str = item.start_time.astimezone(local_tz).strftime("%m月%d日")

        lines = [f"提醒：{job.title}", f"时间：{date_str} {start_str} - {end_str}"]
        if item.location:
            lines.append(f"地点：{item.location}")

        return "\n".join(lines)

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
                content=self._build_message(job),
                user_id=job.user_id,
            )
            if log.status == "sent":
                job.status = ReminderStatus.FIRED.value
                job.fired_at = current_time
                job.error_message = None
                if log.error_code == "QUEUED":
                    logger.warning(
                        "提醒已进入通道队列: job_id=%s, title=%s, user_id=%s, conversation_id=%s",
                        job.id,
                        job.title,
                        job.user_id,
                        conversation_id,
                    )
                else:
                    logger.info(
                        "提醒发送成功: job_id=%s, title=%s, user_id=%s, conversation_id=%s",
                        job.id,
                        job.title,
                        job.user_id,
                        conversation_id,
                    )
                continue

            job.retry_count += 1
            job.error_message = log.error_message
            logger.error(
                "提醒发送失败: job_id=%s, title=%s, user_id=%s, conversation_id=%s, "
                "error_code=%s, error_message=%s, retry_count=%s/%s",
                job.id,
                job.title,
                job.user_id,
                conversation_id,
                log.error_code,
                log.error_message,
                job.retry_count,
                job.max_retries,
            )
            if job.retry_count >= job.max_retries:
                job.status = ReminderStatus.FAILED.value
                logger.error(
                    "提醒已达最大重试次数，标记为失败: job_id=%s, title=%s, user_id=%s, "
                    "error_code=%s, error_message=%s, retry_count=%s",
                    job.id,
                    job.title,
                    job.user_id,
                    log.error_code,
                    log.error_message,
                    job.retry_count,
                )
        self.db.commit()
        return jobs
