from __future__ import annotations

import hashlib
import logging

from app.core.cache import cache_delete, cache_delete_pattern

logger = logging.getLogger(__name__)


def invalidate_user_events(user_id: str) -> None:
    logger.info("失效用户日程缓存 user_id=%s", user_id)
    cache_delete_pattern(f"schedule:user:{user_id}:events:*")


def invalidate_user_tasks(user_id: str) -> None:
    logger.info("失效用户任务缓存 user_id=%s", user_id)
    cache_delete_pattern(f"schedule:user:{user_id}:tasks:*")


def invalidate_user_conflicts(user_id: str) -> None:
    logger.info("失效用户冲突缓存 user_id=%s", user_id)
    cache_delete_pattern(f"schedule:user:{user_id}:conflicts:*")


def invalidate_user_reminders(user_id: str) -> None:
    logger.info("失效用户提醒缓存 user_id=%s", user_id)
    cache_delete_pattern(f"schedule:user:{user_id}:reminders:*")


def invalidate_user_settings(user_id: str) -> None:
    logger.info("失效用户配置缓存 user_id=%s", user_id)
    cache_delete_pattern(f"schedule:user:{user_id}:settings")


def invalidate_system_settings() -> None:
    logger.info("失效系统设置缓存")
    cache_delete_pattern("schedule:system:settings")


def invalidate_weather(city: str | None = None) -> None:
    if city:
        city_hash = hashlib.md5(city.encode()).hexdigest()[:12]
        logger.info("失效天气缓存 city=%s", city)
        cache_delete(f"schedule:weather:{city_hash}")
    else:
        logger.info("失效全部天气缓存")
        cache_delete_pattern("schedule:weather:*")

