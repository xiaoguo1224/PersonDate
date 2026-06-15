from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.system import SystemSetting
from app.schemas.common import ApiResponse
from app.services.system_setting_service import SystemSettingService

router = APIRouter(tags=["weather"])

# 天气数据缓存，格式：{cache_key: {"data": {...}, "expires_at": datetime}}
_weather_cache: dict[str, dict[str, Any]] = {}
CACHE_DURATION = timedelta(hours=12)  # 缓存12小时


def _get_setting_value(db: Session, key: str) -> str | None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if not setting:
        return None
    service = SystemSettingService(db)
    if not service._is_configured(setting):
        return None
    return service._decode_value(setting)


async def _fetch_openweathermap(lat: float, lon: float, api_key: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "metric",
                "lang": "zh_cn",
            },
        )
        response.raise_for_status()
        data = response.json()

    return {
        "city": data["name"],
        "temperature": round(data["main"]["temp"]),
        "description": data["weather"][0]["description"],
        "humidity": data["main"]["humidity"],
        "wind_speed": round(data["wind"]["speed"] * 3.6),
    }


async def _fetch_amap(lat: float, lon: float, api_key: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        geo_response = await client.get(
            "https://restapi.amap.com/v3/geocode/regeo",
            params={
                "key": api_key,
                "location": f"{lon},{lat}",
                "extensions": "base",
            },
        )
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if geo_data.get("status") != "1":
            raise Exception("高德地理编码失败")

        adcode = geo_data["regeocode"]["addressComponent"]["adcode"]
        city = geo_data["regeocode"]["addressComponent"]["city"]
        if not city:
            city = geo_data["regeocode"]["addressComponent"]["province"]

        weather_response = await client.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={
                "key": api_key,
                "city": adcode,
                "extensions": "base",
            },
        )
        weather_response.raise_for_status()
        weather_data = weather_response.json()

        if weather_data.get("status") != "1":
            raise Exception("高德天气查询失败")

        live = weather_data["lives"][0]

    return {
        "city": city or live.get("city", "未知"),
        "temperature": int(live.get("temperature", 0)),
        "description": live.get("weather", "未知"),
        "humidity": int(live.get("humidity", 0)),
        "wind_speed": int(live.get("windpower", 0)),
    }


@router.get("/weather")
async def get_weather(
    lat: float,
    lon: float,
    db: Session = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    provider = _get_setting_value(db, "WEATHER_API_PROVIDER") or "openweathermap"
    api_key = _get_setting_value(db, "WEATHER_API_KEY")

    if not api_key:
        raise HTTPException(status_code=400, detail="天气 API Key 未配置")

    # 生成缓存键，使用经纬度的前4位小数（约11米精度）
    cache_key = f"{provider}_{lat:.4f}_{lon:.4f}"
    now = datetime.now(UTC)

    # 检查缓存是否有效
    if cache_key in _weather_cache:
        cached = _weather_cache[cache_key]
        if now < cached["expires_at"]:
            return ApiResponse(data=cached["data"])

    try:
        if provider == "amap":
            weather_data = await _fetch_amap(lat, lon, api_key)
        else:
            weather_data = await _fetch_openweathermap(lat, lon, api_key)

        # 更新缓存
        _weather_cache[cache_key] = {
            "data": weather_data,
            "expires_at": now + CACHE_DURATION,
        }

        return ApiResponse(data=weather_data)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="天气数据获取失败") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"天气数据获取失败: {str(e)}") from e
