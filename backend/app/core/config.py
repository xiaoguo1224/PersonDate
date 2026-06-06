from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default="sqlite+pysqlite:///./app.db", alias="DATABASE_URL")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    admin_password: str = Field(default="change-me", alias="ADMIN_PASSWORD")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    default_timezone: str = Field(default="Asia/Shanghai", alias="DEFAULT_TIMEZONE")
    reminder_scan_interval_seconds: int = Field(default=10, alias="REMINDER_SCAN_INTERVAL_SECONDS")
    wechat_poll_interval_seconds: int = Field(default=5, alias="WECHAT_POLL_INTERVAL_SECONDS")
    wechat_channel_base_url: str | None = Field(default=None, alias="WECHAT_CHANNEL_BASE_URL")
    wechat_channel_token: str | None = Field(default=None, alias="WECHAT_CHANNEL_TOKEN")
    cors_allow_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOW_ORIGINS",
    )
    weather_api_provider: str = Field(default="qweather", alias="WEATHER_API_PROVIDER")
    weather_api_key: str = Field(default="", alias="WEATHER_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
