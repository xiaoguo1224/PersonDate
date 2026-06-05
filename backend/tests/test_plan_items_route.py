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


def _build_client_and_headers():
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
    setup.create_owner(
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

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def test_plan_item_crud_and_day_plan_listing() -> None:
    client, headers = _build_client_and_headers()
    create_response = client.post(
        "/api/plan-items",
        headers=headers,
        json={
            "plan_date": "2026-06-06",
            "title": "写论文",
            "item_type": "manual",
            "start_time": "2026-06-06T17:00:00+08:00",
            "end_time": "2026-06-06T19:00:00+08:00",
            "status": "planned",
            "is_flexible": True,
            "sort_order": 1,
        },
    )
    assert create_response.status_code == 200
    created_body = create_response.json()["data"]
    plan_item_id = created_body["id"]
    assert created_body["title"] == "写论文"
    assert created_body["item_type"] == "manual"
    assert created_body["is_flexible"] is True

    day_plan_response = client.get("/api/day-plans/2026-06-06", headers=headers)
    assert day_plan_response.status_code == 200
    day_plan_body = day_plan_response.json()["data"]
    assert day_plan_body["items"][0]["id"] == plan_item_id
    assert day_plan_body["items"][0]["title"] == "写论文"

    update_response = client.patch(
        f"/api/plan-items/{plan_item_id}",
        headers=headers,
        json={
            "title": "写论文初稿",
            "start_time": "2026-06-06T18:00:00+08:00",
            "end_time": "2026-06-06T20:00:00+08:00",
            "item_type": "task",
            "status": "in_progress",
            "is_flexible": False,
            "sort_order": 2,
        },
    )
    assert update_response.status_code == 200
    updated_body = update_response.json()["data"]
    assert updated_body["title"] == "写论文初稿"
    assert updated_body["item_type"] == "task"
    assert updated_body["status"] == "in_progress"

    complete_response = client.patch(f"/api/plan-items/{plan_item_id}/complete", headers=headers)
    assert complete_response.status_code == 200
    completed_body = complete_response.json()["data"]
    assert completed_body["status"] == "completed"

    delete_response = client.delete(f"/api/plan-items/{plan_item_id}", headers=headers)
    assert delete_response.status_code == 200
    deleted_body = delete_response.json()["data"]
    assert deleted_body["status"] == "cancelled"

    final_day_plan_response = client.get("/api/day-plans/2026-06-06", headers=headers)
    assert final_day_plan_response.status_code == 200
    final_items = final_day_plan_response.json()["data"]["items"]
    assert final_items[0]["status"] == "cancelled"
