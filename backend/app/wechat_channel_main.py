from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.core.scheduler import build_wechat_channel_scheduler
from app.core.wechat_channel import attach_wechat_channel_client, close_wechat_channel_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    attach_wechat_channel_client(app)
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
