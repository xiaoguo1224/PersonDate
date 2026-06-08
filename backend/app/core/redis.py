from __future__ import annotations

import logging
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        _redis_client.ping()
        logger.info("Redis 连接成功: %s", settings.redis_url)
        return _redis_client
    except (redis.ConnectionError, redis.TimeoutError) as exc:
        logger.warning("Redis 连接失败，降级为无缓存模式: %s", exc)
        _redis_client = None
        return None


def reset_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.close()
        except Exception:
            pass
    _redis_client = None
