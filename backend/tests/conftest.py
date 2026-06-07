from __future__ import annotations

# MUST be first: override DATABASE_URL before any app imports
import os

os.environ["DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/schedule_agent_test"

import json
import re
from collections.abc import Generator
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routes import api_router
from app.core.config import get_settings
from app.schemas.auth import LoginRequest
from app.schemas.setup import OwnerInitRequest
from app.services.auth_service import AuthService
from app.services.setup_service import SetupService

TEST_DB_NAME = "schedule_agent_test"
DB_URL = f"postgresql+psycopg://postgres:postgres@localhost:5432/{TEST_DB_NAME}"
ADMIN_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"


def _create_test_database() -> None:
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()


def _drop_test_database() -> None:
    admin_engine = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    admin_engine.dispose()


def _run_migrations() -> None:
    """Create all tables from model definitions.

    Uses Base.metadata.create_all directly instead of alembic upgrade
    because the migration chain has a pre-existing issue: 0001 uses
    create_all (which creates columns from current models) and 0002 tries
    to add_column for columns that already exist.

    For test/scratch databases this is the correct approach - there is no
    legacy data to migrate.
    """
    from app.db.base import Base

    engine = create_engine(DB_URL, future=True)
    Base.metadata.create_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_db() -> Generator[None, None, None]:
    _create_test_database()
    _run_migrations()
    yield
    _drop_test_database()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(DB_URL, future=True)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, autoflush=False, autocommit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def app(db_session: Session) -> FastAPI:
    _app = FastAPI()
    _app.include_router(api_router)

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    _app.dependency_overrides[get_db] = _override_get_db
    return _app


@pytest.fixture()
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def owner(db_session: Session) -> Any:
    setup = SetupService(db_session)
    o = setup.create_owner(
        OwnerInitRequest(display_name="主用户", email="owner@example.com")
    )
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture()
def admin_token(owner: Any, db_session: Session) -> str:
    settings = get_settings()
    auth = AuthService(db_session)
    _, token = auth.login(
        LoginRequest(username="admin", password=settings.admin_password)
    )
    db_session.commit()
    return token


@pytest.fixture()
def member(db_session: Session) -> Any:
    from app.services.user_service import UserService

    m = UserService(db_session).create_user(
        username="member1",
        password="member123",
        role="member",
        display_name="成员一号",
    )
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture()
def member_token(member: Any, db_session: Session) -> str:
    auth = AuthService(db_session)
    _, token = auth.login(LoginRequest(username="member1", password="member123"))
    db_session.commit()
    return token


# FakeLLMClient for Agent tests

from app.agent.graph import SchedulePlanningGraph  # noqa: E402


class FakeLLMClient:
    def chat_json(self, *, system_prompt: str, user_prompt: str, schema):
        payload = json.loads(user_prompt)
        message = payload["message"]
        current_time = datetime.fromisoformat(payload["current_time"])
        timezone = payload["timezone"]
        intent = self._classify(message)

        if schema.__name__ == "IntentDecision":
            return schema.model_validate(
                {
                    "intent": intent,
                    "confidence": 0.99,
                    "reason": f"根据用户消息判断为 {intent}",
                }
            )
        if schema.__name__ == "MessageExtraction":
            return schema.model_validate(
                self._extract(message, current_time, timezone, intent)
            )
        raise TypeError(f"Unsupported schema: {schema.__name__}")

    def _classify(self, message: str) -> str:
        if message in {"确认", "确认一下"}:
            return "confirm_plan"
        if "提醒" in message and not self._time_pattern.search(message):
            return "ask_user_clarification"
        if any(word in message for word in ("删除", "取消日程", "移除")):
            return "delete_scheduled_item"
        if any(word in message for word in ("改", "修改", "调整")) and "安排" not in message:
            return "update_scheduled_item"
        if any(word in message for word in ("有什么安排", "查看", "查询")):
            return "query_scheduled_items"
        if any(word in message for word in ("帮我安排", "安排一下", "生成计划", "计划一下")):
            return "plan_day"
        if any(word in message for word in ("写论文", "任务", "作业", "学习", "整理资料")):
            return "plan_day" if "安排" in message or "计划" in message else "create_task"
        if any(word in message for word in ("开会", "会议", "见面", "吃饭", "上课", "约")):
            return "create_scheduled_item"
        return "unknown"

    def _extract(self, message: str, current_time: datetime, timezone: str, intent: str) -> dict[str, object]:
        plan_date = self._relative_date(message, current_time)
        time_value = self._time_of_day(message)
        duration_minutes = self._duration_minutes(message)
        keyword = self._title_hint(message)

        data: dict[str, object] = {
            "clarification_prompt": None,
            "event_title": None,
            "event_start_time": None,
            "event_end_time": None,
            "remind_before_minutes": 0,
            "query_start_date": None,
            "query_end_date": None,
            "task_title": None,
            "estimated_minutes": None,
            "task_deadline": None,
            "plan_date": plan_date,
            "target_event_keyword": None,
            "target_event_date": plan_date,
            "new_start_time": None,
            "new_end_time": None,
            "priority": "medium",
        }

        if intent == "create_scheduled_item":
            if time_value is None:
                data["clarification_prompt"] = "请补充具体时间，例如'明天下午 3 点开会'。"
                return data
            start_time = self._build_datetime(plan_date, time_value, timezone)
            data["event_title"] = keyword
            data["event_start_time"] = start_time
            data["event_end_time"] = start_time + timedelta(hours=1)
            return data

        if intent == "query_scheduled_items":
            data["query_start_date"] = plan_date
            data["query_end_date"] = plan_date
            return data

        if intent == "create_task":
            data["task_title"] = keyword
            data["estimated_minutes"] = duration_minutes
            if duration_minutes is None:
                data["clarification_prompt"] = "请补充任务时长，例如'明天写论文 2 小时'。"
            return data

        if intent == "plan_day":
            data["task_title"] = keyword
            data["estimated_minutes"] = duration_minutes
            if duration_minutes is None and "安排" not in message and "计划" not in message:
                data["clarification_prompt"] = "请补充任务时长，例如'明天写论文 2 小时'。"
                return data
            return data

        if intent in {"update_scheduled_item", "delete_scheduled_item"}:
            data["target_event_keyword"] = self._target_keyword(message)
            data["target_event_date"] = plan_date
            if intent == "update_scheduled_item":
                new_time = self._update_time(message, timezone, plan_date)
                if new_time is not None:
                    data["new_start_time"] = new_time
                    data["new_end_time"] = new_time + timedelta(hours=1)
                else:
                    data["clarification_prompt"] = "请补充新的时间，例如'改到 4 点'。"
            return data

        if intent == "ask_user_clarification":
            data["clarification_prompt"] = "请告诉我具体提醒时间，例如'明天下午 3 点提醒我写论文'。"
        return data

    def _update_time(self, message: str, timezone: str, plan_date: date) -> datetime | None:
        match = re.search(r"(?:改到|调整到|到)\s*([^\s，。]+)", message)
        if not match:
            return None
        time_value = self._time_of_day(match.group(1))
        if time_value is None:
            return None
        if not any(
            word in match.group(1)
            for word in ("上午", "下午", "晚上", "中午", "凌晨", "早上", "傍晚")
        ):
            if "下午" in message or "晚上" in message:
                if time_value[0] < 12:
                    time_value = (time_value[0] + 12, time_value[1])
        return self._build_datetime(plan_date, time_value, timezone)

    def _target_keyword(self, message: str) -> str:
        if "会议" in message or "开会" in message:
            return "会议"
        if "论文" in message:
            return "写论文"
        if "作业" in message:
            return "作业"
        return "日程"

    def _title_hint(self, message: str) -> str:
        if "开会" in message or "会议" in message:
            return "会议"
        if "写论文" in message or "论文" in message:
            return "写论文"
        if "作业" in message:
            return "作业"
        if "学习" in message:
            return "学习"
        if "整理资料" in message:
            return "整理资料"
        if "吃饭" in message:
            return "吃饭"
        if "见面" in message:
            return "见面"
        return "任务"

    def _relative_date(self, message: str, current_time: datetime) -> date:
        if "后天" in message:
            return current_time.date() + timedelta(days=2)
        if "明天" in message:
            return current_time.date() + timedelta(days=1)
        return current_time.date()

    def _duration_minutes(self, message: str) -> int | None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(小时|h|H|分钟|分)", message)
        if not match:
            return None
        value = float(match.group(1))
        if match.group(2) in {"小时", "h", "H"}:
            return int(value * 60)
        return int(value)

    def _time_of_day(self, message: str) -> tuple[int, int] | None:
        match = self._time_pattern.search(message)
        if not match:
            return None
        period, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text) if minute_text else 0
        if period in {"下午", "晚上", "傍晚"} and hour < 12:
            hour += 12
        if period in {"凌晨", "早上"} and hour == 12:
            hour = 0
        return hour, minute

    def _build_datetime(self, plan_date: date, time_value: tuple[int, int], timezone: str) -> datetime:
        return datetime.combine(
            plan_date,
            time(hour=time_value[0], minute=time_value[1]),
            tzinfo=ZoneInfo(timezone),
        )

    _time_pattern = re.compile(
        r"(?:(上午|下午|晚上|中午|凌晨|早上|傍晚))?\s*(\d{1,2})(?:[:点时](\d{1,2}))?"
    )


@pytest.fixture()
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture()
def graph(db_session: Session, fake_llm_client: FakeLLMClient) -> SchedulePlanningGraph:
    return SchedulePlanningGraph(db_session, llm_client=fake_llm_client)
