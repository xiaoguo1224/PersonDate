from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import suppress

from app.core.scheduler import build_wechat_channel_scheduler
from app.core.wechat_channel import build_wechat_channel_client, close_wechat_channel_client
from app.main import create_app

logger = logging.getLogger(__name__)


def run(*, sleep_fn: Callable[[float], None] = time.sleep) -> None:
    app = create_app()
    client = build_wechat_channel_client()
    scheduler = None
    if client is None:
        logger.warning("WECHAT_CHANNEL_BASE_URL 未配置，微信通道进程进入空闲模式")
    else:
        app.state.wechat_sender = client
        app.state.wechat_updates_client = client
        scheduler = build_wechat_channel_scheduler(
            updates_client_provider=lambda: client,
        )
        scheduler.start()
        app.state.wechat_channel_scheduler = scheduler
    try:
        while True:
            sleep_fn(1)
    except KeyboardInterrupt:
        pass
    finally:
        if scheduler is not None:
            with suppress(Exception):
                scheduler.shutdown(wait=False)
        close_wechat_channel_client(app)


if __name__ == "__main__":
    run()
