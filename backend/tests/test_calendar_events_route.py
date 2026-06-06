from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db.base import Base
from app.main import create_app
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService


def test_list_calendar_events_can_filter_by_date() -> None:
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

    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for payload in (
        {
            "title": "6日会议",
            "description": "过滤测试",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
        {
            "title": "7日会议",
            "description": "过滤测试",
            "start_time": "2026-06-07T15:00:00+08:00",
            "end_time": "2026-06-07T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
        },
    ):
        response = client.post("/api/calendar-events", headers=headers, json=payload)
        assert response.status_code == 200

    response = client.get(
        "/api/calendar-events?start_date=2026-06-06&end_date=2026-06-06",
        headers=headers,
    )

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]["items"]] == ["6日会议"]


def test_past_calendar_event_is_marked_completed() -> None:
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

    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/calendar-events",
        headers=headers,
        json={
            "title": "历史会议",
            "description": "已结束",
            "start_time": "2025-06-06T15:00:00+08:00",
            "end_time": "2025-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
    )
    assert response.status_code == 200

    list_response = client.get(
        "/api/calendar-events?start_date=2025-06-06&end_date=2025-06-06",
        headers=headers,
    )
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "历史会议"
    assert items[0]["status"] == "completed"
