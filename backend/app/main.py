from fastapi import FastAPI

from app.api.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="微信智能日程规划 Agent", version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
