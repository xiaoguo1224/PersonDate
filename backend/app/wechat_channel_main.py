from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.core.wechat_channel import attach_wechat_channel_client, close_wechat_channel_client
from wechat_channel.poller import PollerManager

logger = logging.getLogger(__name__)


def _start_poller_manager(app: FastAPI) -> PollerManager:
    """Start PollerManager for all active WeChat accounts.

    Extracted as a module-level function so it can be monkeypatched in tests.
    """
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.wechat_channel_service import WechatChannelService

    settings = get_settings()
    poller_manager = PollerManager(db_url=settings.database_url)
    app.state.poller_manager = poller_manager

    db = SessionLocal()
    try:
        service = WechatChannelService(db)
        accounts = [
            (a.account_id, a.bot_token, a.cursor)
            for a in service.list_active_accounts()
        ]
        poller_manager.start_all(accounts)
    finally:
        db.close()
    return poller_manager


def _refresh_poller_manager(app: FastAPI) -> None:
    """定时刷新 PollerManager，加载新绑定的账号。"""
    from app.db.session import SessionLocal
    from app.services.wechat_channel_service import WechatChannelService

    poller_manager: PollerManager | None = getattr(app.state, "poller_manager", None)
    if poller_manager is None:
        return

    db = SessionLocal()
    try:
        service = WechatChannelService(db)
        accounts = [
            (a.account_id, a.bot_token, a.cursor)
            for a in service.list_active_accounts()
        ]
        poller_manager.refresh(accounts)
    except Exception:
        logger.exception("刷新 PollerManager 失败")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    attach_wechat_channel_client(app)

    # 启动 PollerManager（负责 iLink 长轮询写入 inbound_messages 表）
    poller_manager = _start_poller_manager(app)
    app.state.poller_manager = poller_manager

    # 添加定时刷新任务，每 30 秒检查新账号
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _refresh_poller_manager,
        trigger="interval",
        seconds=30,
        id="refresh-poller",
        replace_existing=True,
        args=[app],
    )
    scheduler.start()
    app.state.poller_scheduler = scheduler

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        poller_manager.stop_all()
        close_wechat_channel_client(app)


def run(*, serve_fn: Callable[..., object] = uvicorn.run) -> None:
    serve_fn(
        "app.wechat_channel_app:app",
        host="0.0.0.0",
        port=18789,
        log_level="info",
    )


if __name__ == "__main__":
    run()
