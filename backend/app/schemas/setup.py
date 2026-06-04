from pydantic import BaseModel, EmailStr, Field


class OwnerInitRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=255)
    display_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
