from __future__ import annotations

from collections.abc import Callable

import uvicorn


def run(*, serve_fn: Callable[..., object] = uvicorn.run) -> None:
    serve_fn(
        "app.wechat_channel_app:app",
        host="0.0.0.0",
        port=18789,
        log_level="info",
    )


if __name__ == "__main__":
    run()
