from __future__ import annotations

from fastapi import FastAPI

from app.wechat_channel_routes import router as wechat_channel_router


def create_wechat_channel_app() -> FastAPI:
    app = FastAPI(title="微信通道服务", version="0.1.0")
    app.include_router(wechat_channel_router)
    return app


app = create_wechat_channel_app()
