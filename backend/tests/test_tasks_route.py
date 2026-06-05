from __future__ import annotations

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
from app.services.task_service import TaskService


def test_list_tasks_returns_items() -> None:
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
    owner = setup.create_owner(
        OwnerInitRequest(
            display_name="主用户",
            email="owner@example.com",
        )
    )
    session.commit()

    auth = AuthService(session)
    settings = get_settings()
    _, token = auth.login(LoginRequest(username="admin", password=settings.admin_password))
    session.commit()

    TaskService(session).create_task(
        user_id=owner.id,
        title="写论文",
        description=None,
        estimated_minutes=120,
        deadline=None,
        priority="high",
    )
    session.commit()

    client = TestClient(app)
    response = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"][0]["title"] == "写论文"
