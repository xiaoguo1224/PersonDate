from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


def _empty_str_to_none(value: Any) -> Any:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)


class RegisterWithInviteRequest(BaseModel):
    invite_code: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=255)
    display_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None

    @field_validator("display_name", "email", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_str_to_none(value)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    status: str
    default_timezone: str | None = None
