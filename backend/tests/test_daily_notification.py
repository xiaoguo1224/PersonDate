from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def service(db_session):
    from app.services.daily_notification_service import DailyNotificationService
    return DailyNotificationService(db_session)


class TestGetDueUsers:
    def test_returns_users_with_matching_time(self, service, db_session):
        from app.models.user import User, UserSettings
        user = User(username="test", display_name="Test", password_hash="hash")
        db_session.add(user)
        db_session.flush()
        settings = UserSettings(
            user_id=user.id,
            daily_plan_push_enabled=True,
            daily_plan_push_time="08:00",
        )
        db_session.add(settings)
        db_session.commit()

        with patch.object(service, '_current_time', return_value="08:00"):
            users = service.get_due_users()
            assert len(users) == 1
            assert users[0].id == user.id

    def test_skips_disabled_users(self, service, db_session):
        from app.models.user import User, UserSettings
        user = User(username="test2", password_hash="hash")
        db_session.add(user)
        db_session.flush()
        settings = UserSettings(
            user_id=user.id,
            daily_plan_push_enabled=False,
            daily_plan_push_time="08:00",
        )
        db_session.add(settings)
        db_session.commit()

        with patch.object(service, '_current_time', return_value="08:00"):
            users = service.get_due_users()
            assert len(users) == 0


class TestBuildMessage:
    def test_builds_message_with_schedule(self, service):
        events = [{"time": "10:00", "title": "产品评审会议", "location": "3楼会议室"}]
        tasks = [{"title": "完成周报", "priority": "高"}]
        msg = service.build_message(
            date=datetime(2026, 6, 7),
            weather={"desc": "晴", "temp": 26, "icon": "☀️"},
            city="北京",
            events=events,
            tasks=tasks,
        )
        assert "2026-06-07" in msg
        assert "北京" in msg
        assert "☀️" in msg
        assert "产品评审会议" in msg
        assert "完成周报" in msg

    def test_builds_empty_message(self, service):
        msg = service.build_message(
            date=datetime(2026, 6, 7),
            weather=None,
            city=None,
            events=[],
            tasks=[],
        )
        assert "暂无日程安排" in msg
        assert "暂无待办任务" in msg


class TestGetWeather:
    def test_caches_weather(self, service):
        from app.services.daily_notification_service import WEATHER_CACHE, WEATHER_CACHE_TIMESTAMP
        WEATHER_CACHE.clear()
        WEATHER_CACHE_TIMESTAMP.clear()

        with patch.object(service, '_fetch_weather_from_api') as mock_fetch:
            mock_fetch.return_value = {"desc": "晴", "temp": 26, "icon": "☀️"}
            result1 = service.get_weather("北京")
            result2 = service.get_weather("北京")
            assert result1 == result2
            assert mock_fetch.call_count == 1  # 第二次走缓存
