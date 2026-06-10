from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.models.enums import ScheduledItemStatus, TaskStatus
from app.models.schedule import TaskItem
from app.models.scheduled_item import ScheduledItem
from app.models.user import User, UserSettings
from app.services.channel_identity_service import ChannelIdentityService

logger = logging.getLogger(__name__)


def _weather_cache_key(city: str) -> str:
    import hashlib

    city_hash = hashlib.md5(city.encode()).hexdigest()[:12]
    return f"schedule:weather:{city_hash}"


class DailyNotificationService:
    """每日安排推送服务。在用户设置的推送时间，查询当天安排和天气，拼装消息并通过微信发送。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _last_push_key(user_id: str) -> str:
        return f"schedule:user:{user_id}:last_daily_push_date"

    def _has_pushed_today(self, user_id: str, today: str) -> bool:
        return cache_get(self._last_push_key(user_id)) == today

    def _mark_push_today(self, user_id: str, today: str) -> None:
        cache_set(self._last_push_key(user_id), today, 86400)

    def get_due_users(self) -> list[User]:
        """查找需要推送的用户：当前时间 >= 推送时间 且 今日尚未推送。"""
        stmt = (
            select(User)
            .join(UserSettings)
            .where(UserSettings.daily_plan_push_enabled.is_(True))
        )
        users = list(self.db.scalars(stmt))
        current_time_utc = datetime.now(UTC)
        due_users: list[User] = []
        for user in users:
            settings = user.settings
            if settings is None:
                continue
            timezone_name = settings.default_timezone or "Asia/Shanghai"
            try:
                local_now = current_time_utc.astimezone(ZoneInfo(timezone_name))
            except Exception:
                local_now = current_time_utc.astimezone(ZoneInfo("Asia/Shanghai"))
            today_str = local_now.strftime("%Y-%m-%d")
            current_time = local_now.strftime("%H:%M")
            push_time = (settings.daily_plan_push_time or "08:00")[:5]
            if current_time >= push_time and not self._has_pushed_today(user.id, today_str):
                due_users.append(user)
        return due_users

    def notify_user(self, user: User) -> bool:
        """向单个用户推送今日安排 + 天气。"""
        logger.info("开始推送用户 user_id=%s", user.id)
        from app.services.wechat_channel_service import WechatChannelService

        events = self._get_today_events(user.id)
        tasks = self._get_today_tasks(user.id)

        settings = self.db.scalar(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        city = settings.city if settings else None
        weather = None
        if city:
            try:
                from app.services.system_setting_service import SystemSettingService
                ss = SystemSettingService(self.db)
                weather = self.get_weather(city, provider=ss.get_value("WEATHER_API_PROVIDER"), api_key=ss.get_value("WEATHER_API_KEY"))
            except Exception:
                logger.exception("获取天气失败: city=%s", city)

        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))
        except Exception:
            timezone_name = "Asia/Shanghai"
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))

        message = self.build_message(
            date=local_now,
            weather=weather,
            city=city,
            events=events,
            tasks=tasks,
        )

        identity = ChannelIdentityService(self.db).get_active_wechat_identity(user.id)
        if identity is None:
            logger.info("用户 %s 没有绑定微信，跳过推送", user.id)
            return False

        wechat_service = WechatChannelService(self.db)
        log = wechat_service.send_text(
            conversation_id=identity.conversation_id,
            content=message,
            user_id=user.id,
        )
        if log.status == "sent":
            today_str = datetime.now(UTC).astimezone(ZoneInfo(settings.default_timezone or "Asia/Shanghai")).strftime("%Y-%m-%d")
            self._mark_push_today(user.id, today_str)
            logger.info("推送成功 user_id=%s conversation_id=%s push_date=%s", user.id, identity.conversation_id, today_str)
            logger.info("推送内容: %s", message.replace('\n', ' | '))
        return log.status == "sent"

    def get_weather(self, city: str, provider: str | None = None, api_key: str | None = None) -> dict[str, Any]:
        """获取城市天气，带 1 小时 Redis 缓存。"""
        cache_key = _weather_cache_key(city)
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug("天气缓存命中 city=%s", city)
            return cached
        logger.debug("天气缓存未命中，调用 API city=%s", city)
        data = self._fetch_weather_from_api(city, provider=provider, api_key=api_key)
        cache_set(cache_key, data, 3600)
        return data

    def build_message(
        self,
        *,
        date: datetime,
        weather: dict[str, Any] | None,
        city: str | None,
        events: list[dict[str, str]],
        tasks: list[dict[str, str]],
    ) -> str:
        """拼装推送消息。"""
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_names[date.weekday()]
        date_str = date.strftime("%Y-%m-%d")

        lines: list[str] = []
        lines.append(f"\U0001f324 早安！今天是 {date_str} {weekday}")
        lines.append("")

        if weather and city:
            icon = weather.get("icon", "\U0001f324")
            desc = weather.get("desc", "")
            temp = weather.get("temp", "?")
            lines.append(f"\U0001f4cd {city} 今日天气：{icon} {desc}  {temp}°C")
            lines.append("")
        elif city:
            lines.append(f"\U0001f4cd {city}")
            lines.append("")

        lines.append("\U0001f4c5 今日安排：")
        if events:
            for event in events:
                loc = f"  \U0001f4cd {event['location']}" if event.get("location") else ""
                lines.append(f"  • {event['time']} - {event['title']}{loc}")
        else:
            lines.append("  （暂无安排）")
        lines.append("")

        lines.append("✅ 待办任务：")
        if tasks:
            for task in tasks:
                priority = task.get("priority", "")
                prio_tag = f"（{priority}优先级）" if priority else ""
                lines.append(f"  • {task['title']}{prio_tag}")
        else:
            lines.append("  （暂无待办任务）")
        lines.append("")

        lines.append("\U0001f4cc 回复我可调整今日安排～")
        return "\n".join(lines)

    # --- Internal ---

    def _get_today_events(self, user_id: str) -> list[dict[str, str]]:
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(UTC).astimezone(local_tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        stmt = (
            select(ScheduledItem)
            .where(
                ScheduledItem.user_id == user_id,
                ScheduledItem.start_time >= start_of_day,
                ScheduledItem.start_time < end_of_day,
                ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
            )
            .order_by(ScheduledItem.start_time.asc())
        )
        results = []
        for item in self.db.scalars(stmt):
            results.append({
                "time": item.start_time.astimezone(local_tz).strftime("%H:%M"),
                "title": item.title,
                "location": item.location or "",
            })
        return results

    def _get_today_tasks(self, user_id: str) -> list[dict[str, str]]:
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(UTC).astimezone(local_tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        stmt = (
            select(TaskItem)
            .where(
                TaskItem.user_id == user_id,
                TaskItem.deadline >= start_of_day,
                TaskItem.deadline < end_of_day,
                TaskItem.status == TaskStatus.PENDING.value,
            )
            .order_by(TaskItem.priority.desc(), TaskItem.created_at.asc())
        )
        results = []
        for task in self.db.scalars(stmt):
            results.append({
                "title": task.title,
                "priority": task.priority,
            })
        return results

    def _fetch_weather_from_api(self, city: str, provider=None, api_key=None) -> dict[str, Any]:
        # Use provided config or fall back to settings
        if api_key is None or provider is None:
            sys_settings = get_settings()
            api_key = api_key or sys_settings.weather_api_key
            provider = provider or sys_settings.weather_api_provider
        api_key = api_key or ""
        if not api_key:
            logger.warning("天气 API Key 未配置")
            return {"desc": "未知", "temp": "?", "icon": "\U0001f324"}

        provider = provider or "qweather"
        if provider == "qweather":
            return self._fetch_qweather(city, api_key)
        elif provider == "openweathermap":
            return self._fetch_openweathermap(city, api_key)
        elif provider == "amap":
            return self._fetch_amap(city, api_key)
        else:
            return {"desc": "未知", "temp": "?", "icon": "\U0001f324"}

    def _fetch_qweather(self, city: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            geo = client.get(
                "https://geoapi.qweather.com/v2/city/lookup",
                params={"location": city, "key": api_key},
            )
            geo.raise_for_status()
            geo_data = geo.json()
            if geo_data.get("code") != "200" or not geo_data.get("location"):
                raise RuntimeError(f"找不到城市: {city}")
            loc_id = geo_data["location"][0]["id"]

            weather = client.get(
                "https://devapi.qweather.com/v7/weather/now",
                params={"location": loc_id, "key": api_key},
            )
            weather.raise_for_status()
            wdata = weather.json()
            if wdata.get("code") != "200":
                raise RuntimeError(f"天气查询失败: {wdata}")

            now_data = wdata.get("now", {})
            return {
                "desc": now_data.get("text", "未知"),
                "temp": now_data.get("temp", "?"),
                "icon": self._qweather_icon_to_emoji(now_data.get("icon", "")),
            }

    def _fetch_openweathermap(self, city: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric", "lang": "zh_cn"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "desc": data["weather"][0]["description"],
                "temp": round(data["main"]["temp"]),
                "icon": self._owm_icon_to_emoji(data["weather"][0]["icon"]),
            }

    @staticmethod
    def _qweather_icon_to_emoji(icon: str) -> str:
        mapping = {
            "100": "☀️", "101": "\U0001f324", "102": "⛅", "103": "\U0001f325",
            "104": "☁️", "150": "\U0001f319", "151": "\U0001f319",
            "300": "\U0001f326", "301": "\U0001f326", "302": "\U0001f327", "303": "\U0001f327",
            "400": "\U0001f328", "401": "\U0001f328", "402": "\U0001f328",
            "500": "\U0001f32b", "501": "\U0001f32b", "502": "\U0001f32b",
            "503": "\U0001f32a", "504": "\U0001f32a",
            "507": "\U0001f3d4", "508": "\U0001f3d4",
        }
        return mapping.get(icon, "\U0001f324")

    @staticmethod
    def _owm_icon_to_emoji(icon: str) -> str:
        mapping = {
            "01d": "☀️", "01n": "\U0001f319", "02d": "\U0001f324", "02n": "\U0001f319",
            "03d": "⛅", "03n": "☁️", "04d": "☁️", "04n": "☁️",
            "09d": "\U0001f327", "09n": "\U0001f327", "10d": "\U0001f326", "10n": "\U0001f327",
            "11d": "⛈", "11n": "⛈", "13d": "\U0001f328", "13n": "\U0001f328",
            "50d": "\U0001f32b", "50n": "\U0001f32b",
        }
        return mapping.get(icon, "\U0001f324")

    def _fetch_amap(self, city: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            geo = client.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"key": api_key, "address": city},
            )
            geo.raise_for_status()
            geo_data = geo.json()
            if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
                raise RuntimeError(f"找不到城市: {city}")
            location = geo_data["geocodes"][0].get("city", city)

            weather = client.get(
                "https://restapi.amap.com/v3/weather/weatherInfo",
                params={"key": api_key, "city": location, "extensions": "base"},
            )
            weather.raise_for_status()
            wdata = weather.json()
            if wdata.get("status") != "1":
                raise RuntimeError(f"天气查询失败: {wdata}")

            live = wdata.get("lives", [{}])[0]
            return {
                "desc": live.get("weather", "未知"),
                "temp": live.get("temperature", "?"),
                "icon": self._amap_icon_to_emoji(live.get("weather", "")),
            }

    @staticmethod
    def _amap_icon_to_emoji(weather: str) -> str:
        mapping = {
            "晴": "☀️", "多云": "⛅", "阴": "☁️",
            "小雨": "🌧", "中雨": "🌧", "大雨": "🌧",
            "雷阵雨": "⛈", "雾": "🌫", "霾": "🌫",
        }
        for key, emoji in mapping.items():
            if key in weather:
                return emoji
        return "🌤"
