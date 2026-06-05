from __future__ import annotations

from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.workers.reminder_worker import ReminderWorker

SessionFactory = Callable[[], Session]
SenderProvider = Callable[[], object | None]


def run_reminder_scan(
    *,
    session_factory: SessionFactory = SessionLocal,
    sender_provider: SenderProvider | None = None,
) -> int:
    db = session_factory()
    try:
        sender = sender_provider() if sender_provider is not None else None
        worker = ReminderWorker(db, sender=sender)
        jobs = worker.run_once()
        return len(jobs)
    finally:
        db.close()


def build_reminder_scheduler(
    *,
    session_factory: SessionFactory = SessionLocal,
    sender_provider: SenderProvider | None = None,
) -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_reminder_scan,
        trigger="interval",
        seconds=settings.reminder_scan_interval_seconds,
        id="reminder-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "session_factory": session_factory,
            "sender_provider": sender_provider,
        },
    )
    return scheduler


def start_reminder_scheduler(
    *,
    app: FastAPI,
    session_factory: SessionFactory = SessionLocal,
) -> BackgroundScheduler:
    def sender_provider() -> object | None:
        return getattr(app.state, "wechat_sender", None)

    scheduler = build_reminder_scheduler(
        session_factory=session_factory,
        sender_provider=sender_provider,
    )
    scheduler.start()
    app.state.reminder_scheduler = scheduler
    return scheduler


def stop_reminder_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "reminder_scheduler", None)
    if scheduler is None:
        return
    scheduler.shutdown(wait=False)
    app.state.reminder_scheduler = None
