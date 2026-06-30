from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import ReminderJob, ReminderStatus
from app.models.enums import ScheduledItemStatus
from app.models.scheduled_item import ScheduledItem
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


def test_list_jobs_supports_trigger_time_descending() -> None:
    session = _build_session()
    service = ReminderService(session)

    session.add_all(
        [
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-1",
                title="最早的提醒",
                trigger_time=datetime.now(UTC) + timedelta(minutes=10),
                status=ReminderStatus.PENDING.value,
            ),
            ReminderJob(
                user_id="user-1",
                target_type="scheduled_item",
                target_id="item-2",
                title="最晚的提醒",
                trigger_time=datetime.now(UTC) + timedelta(hours=2),
                status=ReminderStatus.PENDING.value,
            ),
        ]
    )
    session.commit()

    jobs, total = service.list_jobs("user-1", sort_order="trigger_time_desc", page=1, page_size=10)

    assert total == 2
    assert [job.title for job in jobs] == ["最晚的提醒", "最早的提醒"]


def test_sync_pending_for_scheduled_item_replaces_existing_pending_job() -> None:
    session = _build_session()
    service = ReminderService(session)
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    item = ScheduledItem(
        user_id="user-1",
        title="团队会议",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        timezone="UTC",
        remind_before_minutes=30,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.flush()
    existing_job = ReminderJob(
        user_id="user-1",
        target_type="scheduled_item",
        target_id=item.id,
        title="旧提醒",
        trigger_time=now + timedelta(minutes=10),
        status=ReminderStatus.PENDING.value,
    )
    session.add(existing_job)
    session.flush()

    job = service.sync_pending_for_scheduled_item(item, now=now)

    assert job is not None
    assert job.id != existing_job.id
    assert job.target_id == item.id
    assert job.trigger_time == item.start_time - timedelta(minutes=30)
    assert session.get(ReminderJob, existing_job.id).status == ReminderStatus.CANCELED.value


def test_sync_pending_for_scheduled_item_cancels_when_item_is_not_active() -> None:
    session = _build_session()
    service = ReminderService(session)
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    item = ScheduledItem(
        user_id="user-1",
        title="已取消日程",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        timezone="UTC",
        remind_before_minutes=30,
        status=ScheduledItemStatus.COMPLETED.value,
    )
    session.add(item)
    session.flush()
    existing_job = ReminderJob(
        user_id="user-1",
        target_type="scheduled_item",
        target_id=item.id,
        title="旧提醒",
        trigger_time=now + timedelta(minutes=10),
        status=ReminderStatus.PENDING.value,
    )
    session.add(existing_job)
    session.flush()

    job = service.sync_pending_for_scheduled_item(item, now=now)

    assert job is None
    assert session.get(ReminderJob, existing_job.id).status == ReminderStatus.CANCELED.value


def test_sync_pending_for_scheduled_item_skips_expired_trigger_time() -> None:
    session = _build_session()
    service = ReminderService(session)
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    item = ScheduledItem(
        user_id="user-1",
        title="太晚的提醒",
        start_time=now + timedelta(minutes=10),
        end_time=now + timedelta(hours=1),
        timezone="UTC",
        remind_before_minutes=30,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.flush()
    existing_job = ReminderJob(
        user_id="user-1",
        target_type="scheduled_item",
        target_id=item.id,
        title="旧提醒",
        trigger_time=now + timedelta(minutes=10),
        status=ReminderStatus.PENDING.value,
    )
    session.add(existing_job)
    session.flush()

    job = service.sync_pending_for_scheduled_item(item, now=now)

    assert job is None
    assert session.get(ReminderJob, existing_job.id).status == ReminderStatus.CANCELED.value


def test_sync_pending_for_scheduled_item_cancels_only_scheduled_item_pending_job_when_remind_before_minutes_is_none() -> None:
    session = _build_session()
    service = ReminderService(session)
    now = datetime(2026, 6, 30, 8, 0, tzinfo=UTC)
    item = ScheduledItem(
        user_id="user-1",
        title="未设置提醒的日程",
        start_time=now + timedelta(hours=2),
        end_time=now + timedelta(hours=3),
        timezone="UTC",
        remind_before_minutes=None,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.flush()
    scheduled_item_job = ReminderJob(
        user_id="user-1",
        target_type="scheduled_item",
        target_id=item.id,
        title="日程旧提醒",
        trigger_time=now + timedelta(minutes=20),
        status=ReminderStatus.PENDING.value,
    )
    other_job = ReminderJob(
        user_id="user-1",
        target_type="task",
        target_id=item.id,
        title="任务旧提醒",
        trigger_time=now + timedelta(minutes=25),
        status=ReminderStatus.PENDING.value,
    )
    session.add_all([scheduled_item_job, other_job])
    session.flush()

    job = service.sync_pending_for_scheduled_item(item, now=now)

    assert job is None
    assert session.get(ReminderJob, scheduled_item_job.id).status == ReminderStatus.CANCELED.value
    assert session.get(ReminderJob, other_job.id).status == ReminderStatus.PENDING.value
