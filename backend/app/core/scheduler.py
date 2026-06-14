from __future__ import annotations

from collections.abc import Callable
import logging
from typing import cast

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.daily_notification_service import DailyNotificationService
from app.services.system_setting_service import SystemSettingService
from app.services.wechat_channel_poller import WechatChannelPoller, WechatUpdatesClient
from app.services.wechat_channel_service import WechatChannelService
from app.workers.reminder_worker import ReminderWorker

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
SenderProvider = Callable[[], object | None]
UpdatesClientProvider = Callable[[], object | None]


def _resolve_reminder_scan_interval_seconds(*, session_factory: SessionFactory = SessionLocal) -> int:
    db = session_factory()
    if db is None:
        return get_settings().reminder_scan_interval_seconds
    try:
        try:
            value = SystemSettingService(db).get_value("REMINDER_SCAN_INTERVAL_SECONDS")
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.isdigit():
                parsed = int(value)
                if parsed > 0:
                    return parsed
        except Exception:
            logger.exception("读取数据库提醒扫描间隔失败，回退到环境变量")
        settings = get_settings()
        return settings.reminder_scan_interval_seconds
    finally:
        close = getattr(db, "close", None)
        if callable(close):
            close()


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


def run_wechat_outbound_dispatch_scan(
    *,
    session_factory: SessionFactory = SessionLocal,
) -> int:
    db = session_factory()
    try:
        service = WechatChannelService(db)
        processed = service.dispatch_outbound_messages_once()
        db.commit()
        return processed
    finally:
        db.close()


def build_reminder_scheduler(
    *,
    session_factory: SessionFactory = SessionLocal,
    sender_provider: SenderProvider | None = None,
) -> BackgroundScheduler:
    reminder_scan_interval_seconds = _resolve_reminder_scan_interval_seconds(
        session_factory=session_factory,
    )
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_reminder_scan,
        trigger="interval",
        seconds=reminder_scan_interval_seconds,
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


def run_daily_notification_scan(
    *,
    session_factory: SessionFactory = SessionLocal,
) -> int:
    """检查并执行到点的每日推送。"""
    db = session_factory()
    try:
        service = DailyNotificationService(db)
        users = service.get_due_users()
        pushed_count = 0
        for user in users:
            try:
                if service.notify_user(user):
                    pushed_count += 1
            except Exception:
                logger.exception("推送失败: user=%s", user.id)
        db.commit()
        return pushed_count
    finally:
        db.close()


def build_wechat_channel_scheduler(
    *,
    session_factory: SessionFactory = SessionLocal,
    updates_client_provider: UpdatesClientProvider | None = None,
) -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone="UTC")
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
    scheduler.add_job(
        run_wechat_outbound_dispatch_scan,
        trigger="interval",
        seconds=settings.wechat_poll_interval_seconds,
        id="wechat-outbound-dispatch-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "session_factory": session_factory,
        },
    )
    scheduler.add_job(
        run_daily_notification_scan,
        trigger="interval",
        minutes=1,
        id="daily-notification-scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        kwargs={
            "session_factory": session_factory,
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
