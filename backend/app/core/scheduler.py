from __future__ import annotations

from collections.abc import Callable
from typing import cast

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.wechat_channel_poller import WechatChannelPoller, WechatUpdatesClient
from app.workers.reminder_worker import ReminderWorker

SessionFactory = Callable[[], Session]
SenderProvider = Callable[[], object | None]
UpdatesClientProvider = Callable[[], object | None]


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


def run_wechat_poll_scan(
    *,
    session_factory: SessionFactory = SessionLocal,
    updates_client_provider: UpdatesClientProvider | None = None,
) -> int:
    db = session_factory()
    try:
        if updates_client_provider is None:
            return 0
        updates_client = cast(WechatUpdatesClient | None, updates_client_provider())
        if updates_client is None:
            return 0
        poller = WechatChannelPoller(db, updates_client)
        return poller.poll_active_accounts_once()
    finally:
        db.close()


def build_reminder_scheduler(
    *,
    session_factory: SessionFactory = SessionLocal,
    sender_provider: SenderProvider | None = None,
    updates_client_provider: UpdatesClientProvider | None = None,
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
    scheduler.add_job(
        run_wechat_poll_scan,
        trigger="interval",
        seconds=settings.wechat_poll_interval_seconds,
        id="wechat-poll-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "session_factory": session_factory,
            "updates_client_provider": updates_client_provider,
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

    def updates_client_provider() -> object | None:
        return getattr(app.state, "wechat_updates_client", None)

    scheduler = build_reminder_scheduler(
        session_factory=session_factory,
        sender_provider=sender_provider,
        updates_client_provider=updates_client_provider,
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
