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


def test_detect_conflicts_returns_persisted_ids() -> None:
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
    first_event = client.post(
        "/api/calendar-events",
        headers=headers,
        json={
            "title": "会议A",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
    )
    assert first_event.status_code == 200

    second_event = client.post(
        "/api/calendar-events",
        headers=headers,
        json={
            "title": "会议B",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:30:00+08:00",
            "end_time": "2026-06-06T16:30:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
        },
    )
    assert second_event.status_code == 200

    response = client.post("/api/conflicts/detect", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["items"] == []

    list_response = client.get("/api/conflicts?status=open", headers=headers)
    assert list_response.status_code == 200
    listed_items = list_response.json()["data"]["items"]
    assert len(listed_items) == 1
    assert listed_items[0]["id"]
    assert listed_items[0]["title"] == "日程冲突：会议A 与 会议B"


def test_detect_conflicts_deduplicates_repeated_pairs() -> None:
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
    for payload in (
        {
            "title": "会议A",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
        {
            "title": "会议B",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:30:00+08:00",
            "end_time": "2026-06-06T16:30:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
        },
    ):
        response = client.post("/api/calendar-events", headers=headers, json=payload)
        assert response.status_code == 200

    first_detect = client.post("/api/conflicts/detect", headers=headers)
    second_detect = client.post("/api/conflicts/detect", headers=headers)
    list_response = client.get("/api/conflicts?status=open", headers=headers)

    assert first_detect.status_code == 200
    assert second_detect.status_code == 200
    assert len(first_detect.json()["data"]["items"]) == 0
    assert len(second_detect.json()["data"]["items"]) == 0
    assert len(list_response.json()["data"]["items"]) == 1
    assert list_response.json()["data"]["items"][0]["title"] == "日程冲突：会议A 与 会议B"


def test_deleting_event_resolves_related_conflicts() -> None:
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
    create_one = client.post(
        "/api/calendar-events",
        headers=headers,
        json={
            "title": "开会",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:00:00+08:00",
            "end_time": "2026-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
    )
    assert create_one.status_code == 200
    event_id = create_one.json()["data"]["id"]

    create_two = client.post(
        "/api/calendar-events",
        headers=headers,
        json={
            "title": "API自动化测试 日程 B",
            "description": "测试冲突",
            "start_time": "2026-06-06T15:30:00+08:00",
            "end_time": "2026-06-06T16:30:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
        },
    )
    assert create_two.status_code == 200

    before_delete = client.get("/api/conflicts?status=open", headers=headers)
    assert before_delete.status_code == 200
    assert len(before_delete.json()["data"]["items"]) == 1

    delete_response = client.delete(f"/api/calendar-events/{event_id}", headers=headers)
    assert delete_response.status_code == 200

    after_delete = client.get("/api/conflicts?status=open", headers=headers)
    resolved_response = client.get("/api/conflicts?status=resolved", headers=headers)

    assert after_delete.status_code == 200
    assert resolved_response.status_code == 200
    assert after_delete.json()["data"]["items"] == []
    assert len(resolved_response.json()["data"]["items"]) == 1


def test_list_conflicts_auto_resolves_finished_pairs() -> None:
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
    for payload in (
        {
            "title": "已结束会议A",
            "description": "历史冲突",
            "start_time": "2025-06-06T15:00:00+08:00",
            "end_time": "2025-06-06T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室A",
            "remind_before_minutes": 10,
        },
        {
            "title": "已结束会议B",
            "description": "历史冲突",
            "start_time": "2025-06-06T15:30:00+08:00",
            "end_time": "2025-06-06T16:30:00+08:00",
            "timezone": "Asia/Shanghai",
            "location": "会议室B",
            "remind_before_minutes": 10,
        },
    ):
        response = client.post("/api/calendar-events", headers=headers, json=payload)
        assert response.status_code == 200

    open_response = client.get("/api/conflicts?status=open", headers=headers)
    resolved_response = client.get("/api/conflicts?status=resolved", headers=headers)

    assert open_response.status_code == 200
    assert resolved_response.status_code == 200
    assert open_response.json()["data"]["items"] == []
    resolved_items = resolved_response.json()["data"]["items"]
    assert len(resolved_items) == 1
    assert resolved_items[0]["status"] == "resolved"
