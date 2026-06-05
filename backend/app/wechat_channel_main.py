from __future__ import annotations

import time
from contextlib import suppress

from app.core.scheduler import build_wechat_channel_scheduler
from app.core.wechat_channel import (
    attach_wechat_channel_client,
    close_wechat_channel_client,
)
from app.main import create_app


def run() -> None:
    app = create_app()
    attach_wechat_channel_client(app)
    scheduler = build_wechat_channel_scheduler(
        updates_client_provider=lambda: getattr(
            app.state,
            "wechat_updates_client",
            None,
        ),
    )
    scheduler.start()
    app.state.wechat_channel_scheduler = scheduler
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        with suppress(Exception):
            scheduler.shutdown(wait=False)
        close_wechat_channel_client(app)


if __name__ == "__main__":
    run()
