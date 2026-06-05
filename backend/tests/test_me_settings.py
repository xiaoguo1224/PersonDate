from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import create_app
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService


def test_get_and_update_my_settings() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    setup = SetupService(session)
    setup.create_owner(OwnerInitRequest(display_name="主用户", email="owner@example.com"))
    session.commit()

    auth = AuthService(session)
    settings = get_settings()
    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    session.commit()

    client = TestClient(app)

    get_response = client.get("/api/me/settings", headers={"Authorization": f"Bearer {token}"})
    assert get_response.status_code == 200
    payload = get_response.json()["data"]
    assert payload["default_timezone"] == "Asia/Shanghai"
    assert payload["daily_plan_push_enabled"] is False

    update_response = client.patch(
        "/api/me/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "default_timezone": "UTC",
            "workday_start_time": "08:30:00",
            "workday_end_time": "17:30:00",
            "daily_plan_push_time": "07:45:00",
            "default_remind_before_minutes": 15,
            "daily_plan_push_enabled": True,
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["default_timezone"] == "UTC"
    assert updated["daily_plan_push_enabled"] is True
