from typing import Any

from pydantic import BaseModel, Field, field_validator


def _empty_str_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class UserSettingsResponse(BaseModel):
    default_timezone: str
    workday_start_time: str | None = None
    workday_end_time: str | None = None
    daily_plan_push_time: str | None = None
    default_remind_before_minutes: int | None = None
    daily_plan_push_enabled: bool


class UpdateUserSettingsRequest(BaseModel):
    default_timezone: str | None = Field(default=None, max_length=64)
    workday_start_time: str | None = Field(default=None, max_length=8)
    workday_end_time: str | None = Field(default=None, max_length=8)
    daily_plan_push_time: str | None = Field(default=None, max_length=8)
    default_remind_before_minutes: int | None = Field(default=None, ge=0)
    daily_plan_push_enabled: bool | None = None

    @field_validator(
        "default_timezone",
        "workday_start_time",
        "workday_end_time",
        "daily_plan_push_time",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_str_to_none(value)
