from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ChannelIdentity, ReminderJob, ReminderStatus
from app.workers.reminder_worker import ReminderWorker


class FakeWechatSender:
    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.calls: list[tuple[str, str]] = []

    def send_text(self, conversation_id: str, content: str):  # noqa: ANN001
        self.calls.append((conversation_id, content))
        if self.success:
            return {"success": True, "message_id": "wx_reminder_001"}
        return {"success": False, "error_message": "发送失败"}


def _build_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def test_reminder_worker_sends_due_job_and_marks_fired() -> None:
    session = _build_session()
    sender = FakeWechatSender(success=True)
    identity = ChannelIdentity(
        user_id="user-1",
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)
    session.flush()
    job = ReminderJob(
        user_id="user-1",
        target_type="event",
        target_id="event-1",
        title="项目会议",
        conversation_id="wx_user_001",
        trigger_time=datetime.now(UTC) - timedelta(minutes=1),
        status=ReminderStatus.PENDING.value,
    )
    session.add(job)
    session.commit()

    worker = ReminderWorker(session, sender=sender)
    processed = worker.run_once(now=datetime.now(UTC))
    session.refresh(job)

    assert len(processed) == 1
    assert sender.calls == [("wx_user_001", "提醒：项目会议即将开始。")]
    assert job.status == ReminderStatus.FIRED.value
    assert job.fired_at is not None


def test_reminder_worker_keeps_pending_when_send_fails() -> None:
    session = _build_session()
    sender = FakeWechatSender(success=False)
    identity = ChannelIdentity(
        user_id="user-1",
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)
    session.flush()
    job = ReminderJob(
        user_id="user-1",
        target_type="event",
        target_id="event-1",
        title="项目会议",
        conversation_id="wx_user_001",
        trigger_time=datetime.now(UTC) - timedelta(minutes=1),
        status=ReminderStatus.PENDING.value,
        retry_count=0,
        max_retries=3,
    )
    session.add(job)
    session.commit()

    worker = ReminderWorker(session, sender=sender)
    processed = worker.run_once(now=datetime.now(UTC))
    session.refresh(job)

    assert len(processed) == 1
    assert sender.calls == [("wx_user_001", "提醒：项目会议即将开始。")]
    assert job.status == ReminderStatus.PENDING.value
    assert job.retry_count == 1
    assert job.error_message == "发送失败"
