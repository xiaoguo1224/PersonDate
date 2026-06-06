from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.core.scheduler import build_wechat_channel_scheduler
from app.core.wechat_channel import attach_wechat_channel_client, close_wechat_channel_client
from wechat_channel.poller import PollerManager


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    attach_wechat_channel_client(app)

    # 启动 PollerManager
    poller_manager = _start_poller_manager(app)

    scheduler = None
    updates_client = getattr(app.state, "wechat_updates_client", None)
    if updates_client is not None:
        scheduler = build_wechat_channel_scheduler(
            updates_client_provider=lambda: getattr(app.state, "wechat_updates_client", None),
        )
        scheduler.start()
    app.state.wechat_channel_scheduler = scheduler
    try:
        yield
    finally:
        poller_manager.stop_all()
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        app.state.wechat_channel_scheduler = None
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
