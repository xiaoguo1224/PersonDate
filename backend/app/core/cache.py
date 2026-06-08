from __future__ import annotations

import logging
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600  # 10 分钟


def _make_key(prefix: str, *parts: str) -> str:
    joined = ":".join(parts)
    return f"schedule:{prefix}:{joined}"


def _serialize(value: Any) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)


def _deserialize(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        import json
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cache_get(key: str) -> Any | None:
    r = get_redis()
    if r is None:
        logger.debug("cache_skip key=%s (Redis 不可用)", key)
        return None
    try:
        raw = r.get(key)
        if raw is None:
            logger.debug("cache_miss key=%s", key)
            return None
        logger.debug("cache_hit key=%s", key)
        return _deserialize(raw)
    except Exception as exc:
        logger.warning("cache_get 失败 key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        serialized = _serialize(value)
        r.setex(key, ttl, serialized)
        logger.debug("cache_set key=%s ttl=%d", key, ttl)
    except Exception as exc:
        logger.warning("cache_set 失败 key=%s: %s", key, exc)


def cache_delete(key: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(key)
        logger.info("cache_delete key=%s", key)
    except Exception as exc:
        logger.warning("cache_delete 失败 key=%s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
            logger.info("cache_invalidate pattern=%s count=%d", pattern, len(keys))
    except Exception as exc:
        logger.warning("cache_delete_pattern 失败 pattern=%s: %s", pattern, exc)


def cache_get_or_load(
    key: str,
    loader: callable,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> Any:
    cached = cache_get(key)
    if cached is not None:
        return cached
    logger.debug("cache_load key=%s (调用 loader)", key)
    result = loader()
    if result is not None:
        cache_set(key, result, ttl)
    return result
