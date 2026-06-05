from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.scheduler import build_reminder_scheduler, stop_reminder_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = build_reminder_scheduler()
    scheduler.start()
    app.state.reminder_scheduler = scheduler
    try:
        yield
    finally:
        stop_reminder_scheduler(app)


def create_app() -> FastAPI:
    app = FastAPI(title="微信智能日程规划 Agent", version="0.1.0", lifespan=lifespan)
    settings = get_settings()
    allow_origins = [
        origin.strip()
        for origin in settings.cors_allow_origins.split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
