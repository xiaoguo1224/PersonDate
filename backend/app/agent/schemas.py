from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%dT%H:%M:%S",
    "%Y/%m/%dT%H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
)


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
        logger.warning("无法解析 datetime 字符串: %s", value)
    return None


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            pass
        logger.warning("无法解析 date 字符串: %s", value)
    return None


class IntentDecision(BaseModel):
    intent: Literal[
        "create_scheduled_item",
        "query_scheduled_items",
        "query_free_slots",
        "create_task",
        "plan_day",
        "update_scheduled_item",
        "delete_scheduled_item",
        "confirm_plan",
        "ask_user_clarification",
        "unknown",
    ]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "intent" not in payload and "type" in payload:
            payload["intent"] = payload["type"]
        if isinstance(payload.get("intent"), str):
            intent = payload["intent"].strip().lower()
            payload["intent"] = {
                "schedule": "create_scheduled_item",
                "meeting": "create_scheduled_item",
                "event": "create_scheduled_item",
                "query": "query_scheduled_items",
                "task": "create_task",
                "plan": "plan_day",
                "update": "update_scheduled_item",
                "delete": "delete_scheduled_item",
                "confirm": "confirm_plan",
                "clarify": "ask_user_clarification",
            }.get(intent, payload["intent"])
        return payload

    @field_validator("intent", mode="before")
    @classmethod
    def normalize_intent(cls, value: object) -> str:
        if not isinstance(value, str):
            return "unknown"
        normalized = value.strip().lower()
        aliases = {
            "schedule_meeting": "create_scheduled_item",
            "schedule event": "create_scheduled_item",
            "create schedule": "create_scheduled_item",
            "query_schedule": "query_scheduled_items",
            "query calendar": "query_scheduled_items",
            "query_free_time": "query_free_slots",
            "find_free_time": "query_free_slots",
            "check_availability": "query_free_slots",
            "create_reminder": "ask_user_clarification",
            "ask_clarification": "ask_user_clarification",
            "clarify": "ask_user_clarification",
            "create_task": "create_task",
            "create todo": "create_task",
            "plan_schedule": "plan_day",
            "reschedule": "update_scheduled_item",
            "edit_event": "update_scheduled_item",
            "modify_event": "update_scheduled_item",
            "delete_schedule": "delete_scheduled_item",
            "remove_event": "delete_scheduled_item",
            "confirm": "confirm_plan",
        }
        return aliases.get(normalized, normalized)


class MessageExtraction(BaseModel):
    clarification_prompt: str | None = None
    event_title: str | None = None
    event_start_time: datetime | None = None
    event_end_time: datetime | None = None
    event_location: str | None = None
    remind_before_minutes: int | None = None
    query_start_date: date | None = None
    query_end_date: date | None = None
    task_title: str | None = None
    estimated_minutes: int | None = None
    task_deadline: datetime | None = None
    plan_date: date | None = None
    target_event_keyword: str | None = None
    target_event_date: date | None = None
    new_start_time: datetime | None = None
    new_end_time: datetime | None = None
    priority: str | None = None

    @field_validator("event_start_time", "event_end_time", "task_deadline", "new_start_time", "new_end_time", mode="before")
    @classmethod
    def parse_datetime_field(cls, value: object) -> object:
        result = _parse_datetime(value)
        return result if result is not None else value

    @field_validator("query_start_date", "query_end_date", "plan_date", "target_event_date", mode="before")
    @classmethod
    def parse_date_field(cls, value: object) -> object:
        result = _parse_date(value)
        return result if result is not None else value

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)

        if "clarification_prompt" not in payload and payload.get("prompt"):
            payload["clarification_prompt"] = payload["prompt"]

        if "event_title" not in payload and payload.get("title") is not None:
            payload["event_title"] = payload["title"]
        if "event_location" not in payload and payload.get("location") is not None:
            payload["event_location"] = payload["location"]
        if "task_title" not in payload and payload.get("summary") is not None:
            payload["task_title"] = payload["summary"]
        if "task_title" not in payload and payload.get("title") is not None:
            payload["task_title"] = payload["title"]

        if "event_start_time" not in payload and payload.get("start_time") is not None:
            payload["event_start_time"] = payload["start_time"]
        if "event_end_time" not in payload and payload.get("end_time") is not None:
            payload["event_end_time"] = payload["end_time"]
        if "new_start_time" not in payload and payload.get("new_time") is not None:
            payload["new_start_time"] = payload["new_time"]

        if "query_start_date" not in payload and payload.get("date") is not None:
            payload["query_start_date"] = payload["date"]
        if "query_end_date" not in payload and payload.get("date") is not None:
            payload["query_end_date"] = payload["date"]
        if "target_event_date" not in payload and payload.get("date") is not None:
            payload["target_event_date"] = payload["date"]

        if payload.get("original_time") is not None:
            payload.setdefault("event_start_time", payload["original_time"])
            original_time = payload["original_time"]
            if isinstance(original_time, datetime):
                payload.setdefault("target_event_date", original_time.date())
            elif isinstance(original_time, str):
                payload.setdefault("target_event_date", original_time[:10])
        if payload.get("new_time") is not None:
            payload.setdefault("new_start_time", payload["new_time"])

        event = payload.get("event")
        if isinstance(event, dict):
            if payload.get("event_title") is None and event.get("title") is not None:
                payload["event_title"] = event["title"]
            start = event.get("start_time") or event.get("start")
            end = event.get("end_time") or event.get("end")
            if payload.get("event_start_time") is None and start is not None:
                if isinstance(start, dict):
                    payload["event_start_time"] = start.get("dateTime") or start.get("time")
                else:
                    payload["event_start_time"] = start
            if payload.get("event_end_time") is None and end is not None:
                if isinstance(end, dict):
                    payload["event_end_time"] = end.get("dateTime") or end.get("time")
                else:
                    payload["event_end_time"] = end

        events = payload.get("events")
        if isinstance(events, list) and events:
            first_event = events[0]
            if isinstance(first_event, dict):
                if payload.get("task_title") is None and first_event.get("title") is not None:
                    payload["task_title"] = first_event["title"]
                if payload.get("estimated_minutes") is None:
                    duration_minutes = first_event.get("duration_minutes")
                    if isinstance(duration_minutes, int):
                        payload["estimated_minutes"] = duration_minutes
                start = first_event.get("start") or first_event.get("start_time")
                if payload.get("plan_date") is None and start is not None:
                    if isinstance(start, str):
                        payload["plan_date"] = start[:10]
                    elif isinstance(start, datetime):
                        payload["plan_date"] = start.date()

        if payload.get("summary") is not None:
            if payload.get("event_title") is None:
                payload["event_title"] = payload["summary"]
            if payload.get("task_title") is None:
                payload["task_title"] = payload["summary"]

        return payload
