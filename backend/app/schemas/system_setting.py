from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _empty_str_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class SystemSettingItem(BaseModel):
    key: str
    value: Any | None = None
    is_sensitive: bool
    description: str | None = None
    is_configured: bool
    created_at: datetime
    updated_at: datetime


class SystemSettingListResponse(BaseModel):
    items: list[SystemSettingItem]


class UpdateSystemSettingsRequest(BaseModel):
    LLM_BASE_URL: str | None = Field(default=None, max_length=512)
    LLM_MODEL: str | None = Field(default=None, max_length=128)
    LLM_API_KEY: str | None = Field(default=None, max_length=4096)
    DEFAULT_TIMEZONE: str | None = Field(default=None, max_length=64)
    REMINDER_SCAN_INTERVAL_SECONDS: int | None = Field(default=None, ge=1)
    DEFAULT_REMIND_BEFORE_MINUTES: int | None = Field(default=None, ge=0)
    SYSTEM_DAILY_PUSH_ENABLED: bool | None = None
    WEATHER_API_PROVIDER: str | None = Field(default=None, max_length=32)
    WEATHER_API_KEY: str | None = Field(default=None, max_length=4096)

    @field_validator("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "DEFAULT_TIMEZONE", "WEATHER_API_PROVIDER", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_str_to_none(value)
