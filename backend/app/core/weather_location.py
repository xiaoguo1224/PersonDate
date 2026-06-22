from __future__ import annotations

import hashlib
import re

_CITY_SPLIT_RE = re.compile(r"[\/\\|,，、\s-]+")


def normalize_city_query(city: str) -> str:
    normalized = _CITY_SPLIT_RE.sub("", city.strip())
    return normalized.replace("市辖区", "")


def build_weather_cache_key(
    provider: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    city: str | None = None,
) -> str:
    if city:
        normalized_city = normalize_city_query(city)
        city_hash = hashlib.md5(normalized_city.lower().encode("utf-8")).hexdigest()[:12]
        return f"{provider}_city_{city_hash}"
    if lat is not None and lon is not None:
        return f"{provider}_{lat:.4f}_{lon:.4f}"
    raise ValueError("天气缓存键缺少定位信息")

