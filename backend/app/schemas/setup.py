from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


def _empty_str_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class OwnerInitRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None

    @field_validator("display_name", "email", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_str_to_none(value)
