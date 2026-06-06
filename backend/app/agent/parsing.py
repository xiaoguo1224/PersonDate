from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

RELATIVE_DAY_RE = re.compile(r"(今天|明天|后天)")
TIME_RE = re.compile(r"(?:(上午|下午|晚上|中午|凌晨|早上|傍晚))?\s*(\d{1,2})(?:[:点时](\d{1,2}))?")
DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(小时|h|H|分钟|分)")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def parse_relative_date(text: str, now: datetime) -> date | None:
    match = RELATIVE_DAY_RE.search(text)
    if not match:
        return None
    keyword = match.group(1)
    base = now.date()
    if keyword == "今天":
        return base
    if keyword == "明天":
        return base + timedelta(days=1)
    if keyword == "后天":
        return base + timedelta(days=2)
    return None


def parse_time_of_day(text: str) -> tuple[int, int] | None:
    match = TIME_RE.search(text)
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


def parse_last_time_of_day(text: str) -> tuple[int, int] | None:
    matches = list(TIME_RE.finditer(text))
    if not matches:
        return None
    period, hour_text, minute_text = matches[-1].groups()
    hour = int(hour_text)
    minute = int(minute_text) if minute_text else 0
    if period in {"下午", "晚上", "傍晚"} and hour < 12:
        hour += 12
    if period in {"凌晨", "早上"} and hour == 12:
        hour = 0
    return hour, minute


def parse_duration_minutes(text: str) -> int | None:
    match = DURATION_RE.search(text)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit in {"小时", "h", "H"}:
        return int(value * 60)
    return int(value)


def build_datetime(plan_date: date, hour: int, minute: int, tz_name: str) -> datetime:
    return datetime.combine(plan_date, time(hour=hour, minute=minute), tzinfo=ZoneInfo(tz_name))


def extract_keyword_after_time(text: str) -> str | None:
    cleaned = re.sub(
        r"(今天|明天|后天|上午|下午|晚上|中午|凌晨|早上|傍晚|\d{1,2}(?:[:点时]\d{1,2})?)", "", text
    )
    cleaned = re.sub(r"[，。,.!！?？\s]+", "", cleaned)
    cleaned = cleaned.replace("帮我安排一下", "").replace("帮我安排", "")
    cleaned = cleaned.replace("安排一下", "").replace("安排", "")
    cleaned = cleaned.replace("提醒我", "")
    cleaned = cleaned.replace("的", "")
    return cleaned or None


def infer_event_title(text: str) -> str:
    aliases = (
        ("开会", "会议"),
        ("会议", "会议"),
        ("见面", "见面"),
        ("吃饭", "吃饭"),
        ("聚餐", "聚餐"),
        ("上课", "上课"),
        ("约", "约见"),
    )
    for keyword, title in aliases:
        if keyword in text:
            return title
    return extract_keyword_after_time(text) or "安排"


def infer_task_title(text: str) -> str:
    aliases = (
        ("写论文", "写论文"),
        ("论文", "写论文"),
        ("作业", "作业"),
        ("学习", "学习"),
        ("整理资料", "整理资料"),
    )
    for keyword, title in aliases:
        if keyword in text:
            return title
    return extract_keyword_after_time(text) or "任务"


def extract_choice_number(text: str) -> int | None:
    text = text.strip()
    if text in {"1", "2", "3"}:
        return int(text)
    return None
