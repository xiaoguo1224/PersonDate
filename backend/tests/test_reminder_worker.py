from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ChannelIdentity, ReminderJob, ReminderStatus
from app.workers.reminder_worker import ReminderWorker
from wechat_channel.ilink_client import SendResult


class FakeIlinkClient:
    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.calls: list[tuple[str, str]] = []
        self._typing_ticket_cache: dict[str, dict[str, str]] = {}

    def get_typing_ticket(self, bot_token: str, user_id: str, context_token: str) -> str | None:
        return "fake_ticket"

    def send_typing(self, bot_token: str, user_id: str, ticket: str, status: int = 1) -> None:
        pass

    def send_message(self, bot_token: str, to_user_id: str, text: str, context_token: str) -> SendResult:
        self.calls.append((to_user_id, text))
        if self.success:
            return SendResult(success=True)
        return SendResult(success=False, ret=-1, err_msg="mock send failure")


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


def test_reminder_worker_sends_due_job_and_marks_fired(monkeypatch) -> None:
    session = _build_session()
    ilink = FakeIlinkClient(success=True)
    identity = ChannelIdentity(
        user_id="user-1",
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)

    from app.models import WechatAccount
    account = WechatAccount(
        owner_user_id="user-1",
        account_id="wx_acc_001",
        bot_token="fake_bot_token",
        base_url="https://fake.ilink.com",
        status="active",
    )
    session.add(account)
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

    worker = ReminderWorker(session)
    worker.wechat._get_ilink_client = lambda: ilink
    processed = worker.run_once(now=datetime.now(UTC))
    session.refresh(job)

    assert len(processed) == 1
    assert ilink.calls == [("wx_user_001", "提醒：项目会议即将开始。")]
    assert job.status == ReminderStatus.FIRED.value
    assert job.fired_at is not None


def test_reminder_worker_keeps_pending_when_send_fails(monkeypatch) -> None:
    session = _build_session()
    ilink = FakeIlinkClient(success=False)
    identity = ChannelIdentity(
        user_id="user-1",
        channel="wechat",
        channel_user_id="wx_user_001",
        conversation_id="wx_user_001",
        status="active",
    )
    session.add(identity)

    from app.models import WechatAccount
    account = WechatAccount(
        owner_user_id="user-1",
        account_id="wx_acc_001",
        bot_token="fake_bot_token",
        base_url="https://fake.ilink.com",
        status="active",
    )
    session.add(account)
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

    worker = ReminderWorker(session)
    worker.wechat._get_ilink_client = lambda: ilink
    processed = worker.run_once(now=datetime.now(UTC))
    session.refresh(job)

    assert len(processed) == 1
    assert ilink.calls == [("wx_user_001", "提醒：项目会议即将开始。")]
    assert job.status == ReminderStatus.PENDING.value
    assert job.retry_count == 1
    assert job.error_message is not None
