from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import ReminderJob, ReminderStatus
from app.services.reminder_service import ReminderService


def _build_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_list_jobs_orders_by_trigger_time_ascending() -> None:
    session = _build_session()
    service = ReminderService(session)

    session.add_all(
        [
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-1",
                title="晚一些的提醒",
                trigger_time=datetime.now(UTC) + timedelta(hours=2),
                status=ReminderStatus.PENDING.value,
            ),
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-2",
                title="最早的提醒",
                trigger_time=datetime.now(UTC) + timedelta(minutes=30),
                status=ReminderStatus.PENDING.value,
            ),
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-3",
                title="中间的提醒",
                trigger_time=datetime.now(UTC) + timedelta(hours=1),
                status=ReminderStatus.PENDING.value,
            ),
        ]
    )
    session.commit()

    jobs, total = service.list_jobs("user-1", page=1, page_size=10)

    assert total == 3
    assert [job.title for job in jobs] == ["最早的提醒", "中间的提醒", "晚一些的提醒"]


def test_list_jobs_paginates_after_trigger_time_sorting() -> None:
    session = _build_session()
    service = ReminderService(session)

    session.add_all(
        [
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-1",
                title="第一条",
                trigger_time=datetime.now(UTC) + timedelta(minutes=10),
                status=ReminderStatus.PENDING.value,
            ),
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-2",
                title="第二条",
                trigger_time=datetime.now(UTC) + timedelta(minutes=20),
                status=ReminderStatus.PENDING.value,
            ),
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-3",
                title="第三条",
                trigger_time=datetime.now(UTC) + timedelta(minutes=30),
                status=ReminderStatus.PENDING.value,
            ),
        ]
    )
    session.commit()

    jobs, total = service.list_jobs("user-1", page=2, page_size=1)

    assert total == 3
    assert [job.title for job in jobs] == ["第二条"]
