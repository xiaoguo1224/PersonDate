from __future__ import annotations

import json
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import SchedulePlanningGraph
from app.db.base import Base


class FakeLLMClient:
    def chat_json(self, *, system_prompt: str, user_prompt: str, schema):  # noqa: ANN001
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
            return schema.model_validate(self._extract(message, current_time, timezone, intent))
        raise TypeError(f"Unsupported schema: {schema.__name__}")

    def _classify(self, message: str) -> str:
        if message in {"确认", "确认一下"}:
            return "confirm_plan"
        if "提醒" in message and not self._time_pattern.search(message):
            return "ask_user_clarification"
        if any(word in message for word in ("删除", "取消日程", "移除")):
            return "delete_event"
        if any(word in message for word in ("改", "修改", "调整")) and "安排" not in message:
            return "update_event"
        if any(word in message for word in ("有什么安排", "查看", "查询")):
            return "query_events"
        if any(word in message for word in ("帮我安排", "安排一下", "生成计划", "计划一下")):
            return "plan_day"
        if any(word in message for word in ("写论文", "任务", "作业", "学习", "整理资料")):
            return "plan_day" if "安排" in message or "计划" in message else "create_task"
        if any(word in message for word in ("开会", "会议", "见面", "吃饭", "上课", "约")):
            return "create_event"
        return "unknown"

    def _extract(
        self,
        message: str,
        current_time: datetime,
        timezone: str,
        intent: str,
    ) -> dict[str, object]:
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

        if intent == "create_event":
            if time_value is None:
                data["clarification_prompt"] = "请补充具体时间，例如“明天下午 3 点开会”。"
                return data
            start_time = self._build_datetime(plan_date, time_value, timezone)
            data["event_title"] = keyword
            data["event_start_time"] = start_time
            data["event_end_time"] = start_time + timedelta(hours=1)
            return data

        if intent == "query_events":
            data["query_start_date"] = plan_date
            data["query_end_date"] = plan_date
            return data

        if intent == "create_task":
            data["task_title"] = keyword
            data["estimated_minutes"] = duration_minutes
            if duration_minutes is None:
                data["clarification_prompt"] = "请补充任务时长，例如“明天写论文 2 小时”。"
            return data

        if intent == "plan_day":
            data["task_title"] = keyword
            data["estimated_minutes"] = duration_minutes
            if duration_minutes is None and "安排" not in message and "计划" not in message:
                data["clarification_prompt"] = "请补充任务时长，例如“明天写论文 2 小时”。"
                return data
            return data

        if intent in {"update_event", "delete_event"}:
            data["target_event_keyword"] = self._target_keyword(message)
            data["target_event_date"] = plan_date
            if intent == "update_event":
                new_time = self._update_time(message, timezone, plan_date)
                if new_time is not None:
                    data["new_start_time"] = new_time
                    data["new_end_time"] = new_time + timedelta(hours=1)
                else:
                    data["clarification_prompt"] = "请补充新的时间，例如“改到 4 点”。"
            return data

        if intent == "ask_user_clarification":
            data["clarification_prompt"] = "请告诉我具体提醒时间，例如“明天下午 3 点提醒我写论文”。"
        return data

    def _update_time(
        self,
        message: str,
        timezone: str,
        plan_date: date,
    ) -> datetime | None:
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

    def _build_datetime(
        self,
        plan_date: date,
        time_value: tuple[int, int],
        timezone: str,
    ) -> datetime:
        return datetime.combine(
            plan_date,
            time(hour=time_value[0], minute=time_value[1]),
            tzinfo=ZoneInfo(timezone),
        )

    _time_pattern = re.compile(
        r"(?:(上午|下午|晚上|中午|凌晨|早上|傍晚))?\s*(\d{1,2})(?:[:点时](\d{1,2}))?"
    )


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_llm_client():
    return FakeLLMClient()


@pytest.fixture()
def graph(db_session, fake_llm_client):
    return SchedulePlanningGraph(db_session, llm_client=fake_llm_client)
