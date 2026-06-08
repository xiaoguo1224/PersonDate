# Redis 缓存层实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 Redis 缓存层 + 数据库索引修复 + 前端 SWR，解决 Dashboard 今日页加载缓慢问题。

**Architecture:** 后端通过 CacheManager 在 Service 层做查询缓存（写时失效 + TTL 兜底），前端用 SWR 做请求去重和客户端缓存，Redis 不可用时自动降级为直接查库。

**Tech Stack:** redis-py, SWR, Alembic, SQLAlchemy 2.x, FastAPI, Next.js

---

## Task 1: Redis 基础设施 — 连接管理

**Files:**
- Create: `backend/app/core/redis.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: 添加 REDIS_URL 配置项**

修改 `backend/app/core/config.py`，在 `Settings` 类中新增 `redis_url` 字段：

```python
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
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: 更新 .env.example**

在 `backend/.env.example` 末尾添加：

```
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 3: 创建 Redis 连接管理**

创建 `backend/app/core/redis.py`：

```python
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
```

- [ ] **Step 4: 验证连接模块可导入**

Run: `cd backend && uv run python -c "from app.core.redis import get_redis; print('import ok')"`
Expected: `import ok`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/redis.py backend/app/core/config.py backend/.env.example
git commit -m "feat(cache): 添加 Redis 连接管理模块和配置项"
```

---

## Task 2: CacheManager — 统一缓存读写接口

**Files:**
- Create: `backend/app/core/cache.py`

- [ ] **Step 1: 创建 CacheManager**

创建 `backend/app/core/cache.py`：

```python
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 600  # 10 分钟


def _make_key(prefix: str, *parts: str) -> str:
    joined = ":".join(parts)
    return f"schedule:{prefix}:{joined}"


def _serialize(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _deserialize(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def cache_get(key: str) -> Any | None:
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        if raw is None:
            return None
        return _deserialize(raw)
    except Exception as exc:
        logger.debug("cache_get 失败 key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL_SECONDS) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        serialized = _serialize(value)
        r.setex(key, ttl, serialized)
    except Exception as exc:
        logger.debug("cache_set 失败 key=%s: %s", key, exc)


def cache_delete(key: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception as exc:
        logger.debug("cache_delete 失败 key=%s: %s", key, exc)


def cache_delete_pattern(pattern: str) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception as exc:
        logger.debug("cache_delete_pattern 失败 pattern=%s: %s", pattern, exc)


def cache_get_or_load(
    key: str,
    loader: callable,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> Any:
    cached = cache_get(key)
    if cached is not None:
        return cached
    result = loader()
    if result is not None:
        cache_set(key, result, ttl)
    return result
```

- [ ] **Step 2: 验证模块可导入**

Run: `cd backend && uv run python -c "from app.core.cache import cache_get, cache_set, cache_delete_pattern; print('cache module ok')"`
Expected: `cache module ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/cache.py
git commit -m "feat(cache): 添加 CacheManager 统一缓存读写接口"
```

---

## Task 3: CacheInvalidator — 缓存失效逻辑

**Files:**
- Create: `backend/app/core/cache_invalidator.py`

- [ ] **Step 1: 创建 CacheInvalidator**

创建 `backend/app/core/cache_invalidator.py`：

```python
from __future__ import annotations

import logging

from app.core.cache import cache_delete_pattern

logger = logging.getLogger(__name__)


def invalidate_user_events(user_id: str) -> None:
    cache_delete_pattern(f"schedule:user:{user_id}:events:*")


def invalidate_user_tasks(user_id: str) -> None:
    cache_delete_pattern(f"schedule:user:{user_id}:tasks:*")


def invalidate_user_conflicts(user_id: str) -> None:
    cache_delete_pattern(f"schedule:user:{user_id}:conflicts:*")


def invalidate_user_reminders(user_id: str) -> None:
    cache_delete_pattern(f"schedule:user:{user_id}:reminders:*")


def invalidate_user_settings(user_id: str) -> None:
    cache_delete_pattern(f"schedule:user:{user_id}:settings")


def invalidate_system_settings() -> None:
    cache_delete_pattern("schedule:system:settings")


def invalidate_weather(city: str | None = None) -> None:
    if city:
        from app.core.cache import cache_delete
        import hashlib
        city_hash = hashlib.md5(city.encode()).hexdigest()[:12]
        cache_delete(f"schedule:weather:{city_hash}")
    else:
        cache_delete_pattern("schedule:weather:*")


def invalidate_pending_state(conversation_id: str) -> None:
    from app.core.cache import cache_delete
    cache_delete(f"schedule:agent:pending:{conversation_id}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/cache_invalidator.py
git commit -m "feat(cache): 添加 CacheInvalidator 缓存失效逻辑"
```

---

## Task 4: 数据库索引修复

**Files:**
- Create: `backend/alembic/versions/20260608_add_perf_indexes.py`
- Modify: `backend/app/models/scheduled_item.py`
- Modify: `backend/app/models/schedule.py` (TaskItem 和 ChannelMessageLog)

- [ ] **Step 1: 修改 ScheduledItem 模型添加索引**

修改 `backend/app/models/scheduled_item.py`，添加 `__table_args__`：

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ScheduledItemSource, ScheduledItemStatus


class ScheduledItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_items"
    __table_args__ = (
        Index("ix_scheduled_items_user_start", "user_id", "start_time"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    location: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemSource.MANUAL.value
    )
    source_task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_items.id", ondelete="SET NULL")
    )
    remind_before_minutes: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScheduledItemStatus.ACTIVE.value
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: 修改 TaskItem 模型添加索引**

修改 `backend/app/models/schedule.py` 中的 `TaskItem` 类，添加 `__table_args__`：

```python
class TaskItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "task_items"
    __table_args__ = (
        Index("ix_task_items_user_status", "user_id", "status"),
    )
    # ... 其余字段不变
```

- [ ] **Step 3: 修改 ChannelMessageLog 模型添加索引**

修改 `backend/app/models/channel.py` 中的 `ChannelMessageLog` 类，添加复合索引：

```python
class ChannelMessageLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "channel_message_logs"
    __table_args__ = (
        UniqueConstraint("channel", "account_id", "message_id", name="uq_channel_account_message"),
        Index("ix_message_logs_conversation_dir_time", "conversation_id", "direction", "created_at"),
    )
    # ... 其余字段不变
```

- [ ] **Step 4: 生成 Alembic 迁移文件**

Run: `cd backend && uv run alembic revision --autogenerate -m "add_performance_indexes"`

检查生成的迁移文件，确保包含三个索引的创建。

- [ ] **Step 5: 验证迁移可执行**

Run: `cd backend && uv run alembic upgrade head`
Expected: 成功应用迁移

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/scheduled_item.py backend/app/models/schedule.py backend/app/models/channel.py backend/alembic/versions/*add_perf_indexes*.py
git commit -m "perf(db): 添加 scheduled_items、task_items、channel_message_logs 性能索引"
```

---

## Task 5: 后端缓存接入 — SystemSettingService

**Files:**
- Modify: `backend/app/services/system_setting_service.py`

- [ ] **Step 1: 给 SystemSettingService 添加缓存**

修改 `backend/app/services/system_setting_service.py`，在 `list_settings` 和 `update_settings` 中加入缓存逻辑：

```python
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set, cache_delete
from app.core.cache_invalidator import invalidate_system_settings
from app.core.config import get_settings
from app.models import SystemSetting
from app.schemas.system_setting import UpdateSystemSettingsRequest

_SYSTEM_SETTINGS_CACHE_KEY = "schedule:system:settings"
_SYSTEM_SETTINGS_TTL = 1800  # 30 分钟


@dataclass(frozen=True)
class SystemSettingSpec:
    key: str
    default_value: Any
    description: str
    is_sensitive: bool = False


SYSTEM_SETTING_SPECS: tuple[SystemSettingSpec, ...] = (
    SystemSettingSpec("DEFAULT_TIMEZONE", "Asia/Shanghai", "系统默认时区"),
    SystemSettingSpec("REMINDER_SCAN_INTERVAL_SECONDS", 10, "提醒扫描间隔秒数"),
    SystemSettingSpec("DEFAULT_REMIND_BEFORE_MINUTES", 0, "系统默认提醒提前分钟数"),
    SystemSettingSpec("SYSTEM_DAILY_PUSH_ENABLED", False, "是否启用系统每日推送"),
    SystemSettingSpec("LLM_BASE_URL", None, "LLM Base URL"),
    SystemSettingSpec("LLM_MODEL", None, "LLM 模型名称"),
    SystemSettingSpec("LLM_API_KEY", None, "LLM API Key", True),
    SystemSettingSpec("WEATHER_API_PROVIDER", "openweathermap", "天气 API 提供商 (openweathermap/amap)"),
    SystemSettingSpec("WEATHER_API_KEY", None, "天气 API Key", True),
)


class SystemSettingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._fernet = Fernet(self._fernet_key())

    def _fernet_key(self) -> bytes:
        digest = sha256(self.settings.jwt_secret.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _spec_map(self) -> dict[str, SystemSettingSpec]:
        return {spec.key: spec for spec in SYSTEM_SETTING_SPECS}

    def _encode_value(self, value: Any, *, is_sensitive: bool) -> dict[str, Any]:
        if is_sensitive:
            if value in (None, ""):
                return {"ciphertext": ""}
            ciphertext = self._fernet.encrypt(json.dumps(value, ensure_ascii=False).encode("utf-8"))
            return {"ciphertext": ciphertext.decode("utf-8")}
        return {"value": value}

    def _decode_value(self, setting: SystemSetting) -> Any:
        payload = setting.value if isinstance(setting.value, dict) else {}
        if setting.is_sensitive:
            ciphertext = payload.get("ciphertext")
            if not ciphertext:
                return None
            try:
                decrypted = self._fernet.decrypt(str(ciphertext).encode("utf-8"))
                return json.loads(decrypted.decode("utf-8"))
            except (InvalidToken, json.JSONDecodeError):
                return None
        return payload.get("value")

    def _is_configured(self, setting: SystemSetting) -> bool:
        payload = setting.value if isinstance(setting.value, dict) else {}
        if setting.is_sensitive:
            ciphertext = payload.get("ciphertext")
            return bool(ciphertext)
        return payload.get("value") is not None

    def _seed_defaults(self) -> None:
        for spec in SYSTEM_SETTING_SPECS:
            existing = self.db.scalar(select(SystemSetting).where(SystemSetting.key == spec.key))
            if existing is not None:
                continue
            setting = SystemSetting(
                key=spec.key,
                value=self._encode_value(spec.default_value, is_sensitive=spec.is_sensitive),
                description=spec.description,
                is_sensitive=spec.is_sensitive,
            )
            self.db.add(setting)
        self.db.flush()

    def list_settings(self) -> list[SystemSetting]:
        cached = cache_get(_SYSTEM_SETTINGS_CACHE_KEY)
        if cached is not None:
            # 缓存命中时返回 dict 列表，调用方需兼容
            # 但 list_settings 的调用方通常需要 ORM 对象
            # 所以这里不缓存 ORM 对象，而是缓存 to_public_dict 的结果
            pass
        self._seed_defaults()
        stmt = select(SystemSetting).order_by(SystemSetting.key.asc())
        result = list(self.db.scalars(stmt))
        return result

    def list_settings_public(self) -> list[dict[str, Any]]:
        cached = cache_get(_SYSTEM_SETTINGS_CACHE_KEY)
        if cached is not None:
            return cached
        settings = self.list_settings()
        result = [self.to_public_dict(s) for s in settings]
        cache_set(_SYSTEM_SETTINGS_CACHE_KEY, result, _SYSTEM_SETTINGS_TTL)
        return result

    def get_value(self, key: str) -> Any:
        cached = cache_get(_SYSTEM_SETTINGS_CACHE_KEY)
        if cached is not None:
            for item in cached:
                if item.get("key") == key:
                    return item.get("value")
        setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if setting is None:
            return None
        return self._decode_value(setting)

    def update_settings(self, payload: UpdateSystemSettingsRequest) -> list[SystemSetting]:
        spec_map = self._spec_map()
        self._seed_defaults()
        for field_name in payload.model_fields_set:
            if field_name not in spec_map:
                continue
            spec = spec_map[field_name]
            setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key == spec.key))
            if setting is None:
                setting = SystemSetting(
                    key=spec.key,
                    value=self._encode_value(None, is_sensitive=spec.is_sensitive),
                    description=spec.description,
                    is_sensitive=spec.is_sensitive,
                )
                self.db.add(setting)
            raw_value = getattr(payload, field_name)
            setting.value = self._encode_value(raw_value, is_sensitive=spec.is_sensitive)
            setting.description = spec.description
            setting.is_sensitive = spec.is_sensitive
        self.db.flush()
        invalidate_system_settings()
        return self.list_settings()

    def to_public_dict(self, setting: SystemSetting) -> dict[str, Any]:
        return {
            "key": setting.key,
            "value": None if setting.is_sensitive else self._decode_value(setting),
            "is_sensitive": setting.is_sensitive,
            "description": setting.description,
            "is_configured": self._is_configured(setting),
            "created_at": setting.created_at,
            "updated_at": setting.updated_at,
        }
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/system_setting_service.py
git commit -m "feat(cache): SystemSettingService 接入 Redis 缓存"
```

---

## Task 6: 后端缓存接入 — UserService (UserSettings)

**Files:**
- Modify: `backend/app/services/user_service.py`

- [ ] **Step 1: 给 UserService 的 UserSettings 方法添加缓存**

修改 `backend/app/services/user_service.py`：

```python
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set, cache_delete
from app.core.cache_invalidator import invalidate_user_settings
from app.core.security import hash_password
from app.models import User, UserSettings, UserStatus
from app.schemas.user_settings import UpdateUserSettingsRequest

_USER_SETTINGS_TTL = 1800  # 30 分钟


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def list_users(self) -> list[User]:
        stmt = select(User).where(User.status != UserStatus.DELETED.value)
        return list(self.db.scalars(stmt.order_by(User.created_at.desc())))

    def create_user(
        self,
        *,
        username: str,
        password: str,
        role: str,
        display_name: str | None = None,
        email: str | None = None,
        status: str = UserStatus.ACTIVE.value,
    ) -> User:
        user = User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            display_name=display_name,
            email=email,
            status=status,
        )
        self.db.add(user)
        self.db.flush()
        self.ensure_settings(user.id)
        return user

    def ensure_settings(self, user_id: str) -> UserSettings:
        cache_key = f"schedule:user:{user_id}:settings"
        cached = cache_get(cache_key)
        if cached is not None:
            # 缓存中有 settings 信息，但仍需返回 ORM 对象
            # 直接查库返回，缓存用于其他快速读取场景
            pass
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        if settings:
            return settings
        settings = UserSettings(user_id=user_id)
        self.db.add(settings)
        self.db.flush()
        return settings

    def get_settings_dict(self, user_id: str) -> dict | None:
        cache_key = f"schedule:user:{user_id}:settings"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        if settings is None:
            return None
        result = {
            "user_id": settings.user_id,
            "default_timezone": settings.default_timezone,
            "workday_start_time": str(settings.workday_start_time) if settings.workday_start_time else None,
            "workday_end_time": str(settings.workday_end_time) if settings.workday_end_time else None,
            "daily_plan_push_time": settings.daily_plan_push_time,
            "default_remind_before_minutes": settings.default_remind_before_minutes,
            "daily_plan_push_enabled": settings.daily_plan_push_enabled,
            "city": settings.city,
        }
        cache_set(cache_key, result, _USER_SETTINGS_TTL)
        return result

    def mark_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)

    def disable_user(self, user: User) -> User:
        user.status = UserStatus.DISABLED.value
        return user

    def enable_user(self, user: User) -> User:
        user.status = UserStatus.ACTIVE.value
        return user

    def update_settings(self, user_id: str, payload: UpdateUserSettingsRequest) -> UserSettings:
        settings = self.ensure_settings(user_id)
        if payload.default_timezone is not None:
            settings.default_timezone = payload.default_timezone
        if payload.workday_start_time is not None:
            settings.workday_start_time = payload.workday_start_time
        if payload.workday_end_time is not None:
            settings.workday_end_time = payload.workday_end_time
        if payload.daily_plan_push_time is not None:
            settings.daily_plan_push_time = payload.daily_plan_push_time
        if payload.default_remind_before_minutes is not None:
            settings.default_remind_before_minutes = payload.default_remind_before_minutes
        if payload.daily_plan_push_enabled is not None:
            settings.daily_plan_push_enabled = payload.daily_plan_push_enabled
        invalidate_user_settings(user_id)
        return settings
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/user_service.py
git commit -m "feat(cache): UserService UserSettings 接入 Redis 缓存"
```

---

## Task 7: 后端缓存接入 — ScheduledItemService

**Files:**
- Modify: `backend/app/services/scheduled_item_service.py`

- [ ] **Step 1: 给 ScheduledItemService 添加缓存**

修改 `backend/app/services/scheduled_item_service.py`：

```python
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import UTC

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_events
from app.models.enums import ScheduledItemStatus, TaskStatus
from app.models.scheduled_item import ScheduledItem

_EVENTS_TTL = 600  # 10 分钟


class ScheduledItemService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str = "Asia/Shanghai",
        description: str | None = None,
        location: str | None = None,
        source: str = "manual",
        source_task_id: str | None = None,
        remind_before_minutes: int | None = None,
        status: str = "active",
    ) -> ScheduledItem:
        item = ScheduledItem(
            user_id=user_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            description=description,
            location=location,
            source=source,
            source_task_id=source_task_id,
            remind_before_minutes=remind_before_minutes,
            status=status,
        )
        self.db.add(item)
        self.db.flush()
        invalidate_user_events(user_id)
        return item

    def get(self, user_id: str, item_id: str) -> ScheduledItem | None:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.id == item_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        )
        return self.db.scalar(stmt)

    def list_by_date_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
        status: str | None = None,
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time < end_time,
            ScheduledItem.end_time > start_time,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if status:
            conditions.append(ScheduledItem.status == status)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def list_by_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        cache_key = f"schedule:user:{user_id}:events:date:{plan_date.isoformat()}"
        cached = cache_get(cache_key)
        if cached is not None:
            # 缓存命中时返回 dict 列表，但调用方需要 ORM 对象
            # 此处跳过缓存，直接查库 — 缓存用于 API 层序列化结果
            pass
        start = datetime(plan_date.year, plan_date.month, plan_date.day, tzinfo=UTC)
        end = start.replace(hour=23, minute=59, second=59)
        return self.list_by_date_range(user_id, start, end)

    def list_by_date_cached(self, user_id: str, plan_date: date) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:events:date:{plan_date.isoformat()}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items = self.list_by_date(user_id, plan_date)
        result = [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "start_time": item.start_time.isoformat(),
                "end_time": item.end_time.isoformat(),
                "timezone": item.timezone,
                "location": item.location,
                "source": item.source,
                "source_task_id": item.source_task_id,
                "remind_before_minutes": item.remind_before_minutes,
                "status": item.status,
                "sort_order": item.sort_order,
            }
            for item in items
        ]
        cache_set(cache_key, result, _EVENTS_TTL)
        return result

    def update(
        self,
        item: ScheduledItem,
        title: str | None = None,
        description: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        timezone: str | None = None,
        location: str | None = None,
        remind_before_minutes: int | None = None,
        status: str | None = None,
    ) -> ScheduledItem:
        if title is not None:
            item.title = title
        if description is not None:
            item.description = description
        if start_time is not None:
            item.start_time = start_time
        if end_time is not None:
            item.end_time = end_time
        if timezone is not None:
            item.timezone = timezone
        if location is not None:
            item.location = location
        if remind_before_minutes is not None:
            item.remind_before_minutes = remind_before_minutes
        if status is not None:
            item.status = status
        self.db.flush()
        invalidate_user_events(item.user_id)
        return item

    def mark_completed(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.COMPLETED.value
        self.db.flush()
        invalidate_user_events(item.user_id)
        return item

    def soft_delete(self, item: ScheduledItem) -> ScheduledItem:
        item.status = ScheduledItemStatus.DELETED.value
        self.db.flush()
        invalidate_user_events(item.user_id)
        return item

    def search(
        self, user_id: str, keyword: str, on_date: date | None = None
    ) -> list[ScheduledItem]:
        conditions = [
            ScheduledItem.user_id == user_id,
            ScheduledItem.title.ilike(f"%{keyword}%"),
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ]
        if on_date:
            start = datetime(on_date.year, on_date.month, on_date.day)
            end = start.replace(hour=23, minute=59, second=59)
            conditions.append(ScheduledItem.start_time >= start)
            conditions.append(ScheduledItem.start_time <= end)
        stmt = select(ScheduledItem).where(*conditions).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> int:
        start = datetime(plan_date.year, plan_date.month, plan_date.day)
        end = start.replace(hour=23, minute=59, second=59)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time >= start,
            ScheduledItem.start_time <= end,
            ScheduledItem.status == ScheduledItemStatus.DRAFT.value,
        )
        items = list(self.db.scalars(stmt))
        for item in items:
            item.status = ScheduledItemStatus.ACTIVE.value
        self.db.flush()
        invalidate_user_events(user_id)
        return len(items)

    def list_pending_tasks(self, user_id: str) -> list:
        from app.models.schedule import TaskItem

        stmt = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status == TaskStatus.PENDING.value,
        ).order_by(TaskItem.priority.desc(), TaskItem.deadline.asc().nulls_last())
        return list(self.db.scalars(stmt))

    def list_by_task_id(
        self, user_id: str, task_id: str
    ) -> list[ScheduledItem]:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def generate_day_drafts(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
        existing = self.list_by_date(user_id, plan_date)
        planned_task_ids = {
            si.source_task_id for si in existing if si.source_task_id
        }

        pending_tasks = [
            t for t in self.list_pending_tasks(user_id)
            if t.id not in planned_task_ids
        ]

        if not pending_tasks:
            return []

        base = datetime(plan_date.year, plan_date.month, plan_date.day, 9, 0, tzinfo=UTC)
        created: list[ScheduledItem] = []
        for task in pending_tasks:
            mins = task.estimated_minutes or 60
            slot_start = base
            slot_end = slot_start + timedelta(minutes=mins)

            conflict = False
            for ex in existing:
                if ex.start_time < slot_end and ex.end_time > slot_start:
                    conflict = True
                    base = ex.end_time
                    break
            if conflict:
                continue
            item = self.create(
                user_id=user_id,
                title=task.title,
                start_time=slot_start,
                end_time=slot_end,
                source="plan",
                source_task_id=task.id,
                status="draft",
            )
            created.append(item)
            base = slot_end

        return created
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/scheduled_item_service.py
git commit -m "feat(cache): ScheduledItemService 接入 Redis 缓存"
```

---

## Task 8: 后端缓存接入 — TaskService

**Files:**
- Modify: `backend/app/services/task_service.py`

- [ ] **Step 1: 给 TaskService 添加缓存**

修改 `backend/app/services/task_service.py`，在写操作后调用 `invalidate_user_tasks`：

```python
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_tasks
from app.models import ScheduleSource, TaskItem, TaskStatus
from app.models.enums import ScheduledItemStatus, ScheduledItemSource, TaskScheduleType, TaskTimeType
from app.models.scheduled_item import ScheduledItem

_TASKS_TTL = 600  # 10 分钟

_UNSET = object()


class TaskService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_task(
        self,
        *,
        user_id: str,
        title: str,
        description: str | None = None,
        estimated_minutes: int | None = None,
        deadline: datetime | None = None,
        priority: str = "medium",
        source: str = ScheduleSource.AGENT.value,
        schedule_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        duration_days: int | None = None,
        time_type: str | None = None,
        scheduled_time: time | None = None,
        scheduled_end_time: time | None = None,
    ) -> TaskItem:
        item = TaskItem(
            user_id=user_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            deadline=deadline,
            priority=priority,
            source=source,
            schedule_type=schedule_type,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            time_type=time_type,
            scheduled_time=scheduled_time,
            scheduled_end_time=scheduled_end_time,
        )
        self.db.add(item)
        self.db.flush()
        invalidate_user_tasks(user_id)
        return item

    def list_tasks(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TaskItem], int]:
        base = select(TaskItem).where(
            TaskItem.user_id == user_id,
            TaskItem.status != TaskStatus.DELETED.value,
        )
        if status:
            base = base.where(TaskItem.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            base = base.where(
                (TaskItem.title.ilike(pattern)) | (TaskItem.description.ilike(pattern))
            )
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        items = list(
            self.db.scalars(
                base.order_by(TaskItem.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def list_tasks_cached(self, user_id: str, status: str | None = None) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:tasks:status:{status or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items, _ = self.list_tasks(user_id, status=status, page_size=100)
        result = [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "estimated_minutes": item.estimated_minutes,
                "deadline": item.deadline.isoformat() if item.deadline else None,
                "priority": item.priority,
                "status": item.status,
                "schedule_type": item.schedule_type,
                "start_date": item.start_date.isoformat() if item.start_date else None,
                "end_date": item.end_date.isoformat() if item.end_date else None,
                "duration_days": item.duration_days,
                "time_type": item.time_type,
                "scheduled_time": str(item.scheduled_time) if item.scheduled_time else None,
                "scheduled_end_time": str(item.scheduled_end_time) if item.scheduled_end_time else None,
                "completed_days": item.completed_days,
            }
            for item in items
        ]
        cache_set(cache_key, result, _TASKS_TTL)
        return result

    def get_task(self, user_id: str, task_id: str) -> TaskItem | None:
        stmt = select(TaskItem).where(TaskItem.user_id == user_id, TaskItem.id == task_id)
        return self.db.scalar(stmt)

    def update_task(self, task: TaskItem, **changes: object) -> TaskItem:
        for key, value in changes.items():
            if value is _UNSET:
                continue
            setattr(task, key, value)
        invalidate_user_tasks(task.user_id)
        return task

    def complete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.COMPLETED.value
        task.completed_days = (task.completed_days or 0) + 1
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.COMPLETED.value
        invalidate_user_tasks(task.user_id)
        return task

    def delete_task(self, task: TaskItem) -> TaskItem:
        task.status = TaskStatus.DELETED.value
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == task.user_id,
            ScheduledItem.source_task_id == task.id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
        )
        for item in self.db.scalars(stmt):
            item.status = ScheduledItemStatus.DELETED.value
        invalidate_user_tasks(task.user_id)
        return task

    def complete_task_day(self, task: TaskItem) -> TaskItem:
        task.completed_days = (task.completed_days or 0) + 1
        return task

    def get_dates_for_task(self, task: TaskItem, limit: int = 30) -> list[date]:
        if task.schedule_type == TaskScheduleType.DAILY:
            start = task.start_date or date.today()
            end = task.end_date or (task.deadline.date() if task.deadline else start + timedelta(days=limit - 1))
            return _date_range(start, end)

        if task.schedule_type == TaskScheduleType.WEEKDAYS:
            start = task.start_date or date.today()
            end = task.end_date or (task.deadline.date() if task.deadline else start + timedelta(days=limit - 1))
            return _weekday_range(start, end)

        if task.schedule_type == TaskScheduleType.DURATION_DAYS:
            start = task.start_date or date.today()
            days = task.duration_days or 1
            return _date_range(start, start + timedelta(days=days - 1))

        if task.schedule_type == TaskScheduleType.CUSTOM_RANGE:
            if task.start_date and task.end_date:
                return _date_range(task.start_date, task.end_date)

        return []

    def list_scheduled_items_for_task(
        self, user_id: str, task_id: str
    ) -> list[ScheduledItem]:
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.source_task_id == task_id,
            ScheduledItem.status != ScheduledItemStatus.DELETED.value,
        ).order_by(ScheduledItem.start_time)
        return list(self.db.scalars(stmt))

    def sync_task_to_scheduled_items(
        self,
        task: TaskItem,
        user_id: str,
        timezone: str = "Asia/Shanghai",
    ) -> list[ScheduledItem]:
        from app.services.scheduled_item_service import ScheduledItemService

        si_service = ScheduledItemService(self.db)

        existing = si_service.list_by_task_id(user_id, task.id)
        for item in existing:
            if item.source != ScheduledItemSource.MANUAL.value:
                si_service.soft_delete(item)

        dates = self.get_dates_for_task(task)
        if not dates:
            return []

        mins = task.estimated_minutes or 60
        created: list[ScheduledItem] = []

        for d in dates:
            if task.time_type == TaskTimeType.FIXED and task.scheduled_time is not None:
                start_dt = _combine_local(d, task.scheduled_time, timezone)
                end_dt = (
                    _combine_local(d, task.scheduled_end_time, timezone)
                    if task.scheduled_end_time
                    else start_dt + timedelta(minutes=mins)
                )
                item = si_service.create(
                    user_id=user_id,
                    title=task.title,
                    start_time=start_dt,
                    end_time=end_dt,
                    timezone=timezone,
                    source=ScheduledItemSource.TASK.value,
                    source_task_id=task.id,
                    status=ScheduledItemStatus.ACTIVE.value,
                )
                created.append(item)
            else:
                slot = self._find_next_free_slot(user_id, d, mins, timezone)
                if slot:
                    item = si_service.create(
                        user_id=user_id,
                        title=task.title,
                        start_time=slot[0],
                        end_time=slot[1],
                        timezone=timezone,
                        source=ScheduledItemSource.TASK.value,
                        source_task_id=task.id,
                        status=ScheduledItemStatus.ACTIVE.value,
                    )
                    created.append(item)

        return created

    def reschedule_conflicted_item(
        self,
        user_id: str,
        task: TaskItem,
        item: ScheduledItem,
        timezone: str = "Asia/Shanghai",
    ) -> tuple[bool, ScheduledItem | None]:
        if task.time_type != TaskTimeType.FLEXIBLE:
            return False, None

        item_date = item.start_time.astimezone(_tzinfo(timezone)).date()
        mins = task.estimated_minutes or 60
        slot = self._find_next_free_slot(user_id, item_date, mins, timezone, exclude_id=item.id)
        if not slot:
            return False, None

        from app.services.scheduled_item_service import ScheduledItemService
        si_service = ScheduledItemService(self.db)
        updated = si_service.update(item, start_time=slot[0], end_time=slot[1])
        return True, updated

    def _find_next_free_slot(
        self,
        user_id: str,
        plan_date: date,
        duration_minutes: int,
        timezone: str = "Asia/Shanghai",
        exclude_id: str | None = None,
    ) -> tuple[datetime, datetime] | None:
        day_start = datetime(plan_date.year, plan_date.month, plan_date.day, 8, 0, tzinfo=_tzinfo(timezone))
        day_end = datetime(plan_date.year, plan_date.month, plan_date.day, 22, 0, tzinfo=_tzinfo(timezone))

        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.start_time < day_end,
            ScheduledItem.end_time > day_start,
            ScheduledItem.status.notin_([
                ScheduledItemStatus.DELETED.value,
                ScheduledItemStatus.CANCELLED.value,
            ]),
        )
        if exclude_id:
            stmt = stmt.where(ScheduledItem.id != exclude_id)

        existing = list(self.db.scalars(stmt.order_by(ScheduledItem.start_time)))
        if not existing:
            return day_start, day_start + timedelta(minutes=duration_minutes)

        candidate = day_start
        for ex in existing:
            if candidate + timedelta(minutes=duration_minutes) <= ex.start_time:
                return candidate, candidate + timedelta(minutes=duration_minutes)
            if ex.end_time > candidate:
                candidate = ex.end_time

        if candidate + timedelta(minutes=duration_minutes) <= day_end:
            return candidate, candidate + timedelta(minutes=duration_minutes)

        return None


def _date_range(start: date, end: date) -> list[date]:
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _weekday_range(start: date, end: date) -> list[date]:
    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _combine_local(d: date, t: time, tz_name: str) -> datetime:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(tz_name)
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=tz)


def _tzinfo(tz_name: str):
    from zoneinfo import ZoneInfo
    return ZoneInfo(tz_name)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/task_service.py
git commit -m "feat(cache): TaskService 接入 Redis 缓存"
```

---

## Task 9: 后端缓存接入 — ReminderService

**Files:**
- Modify: `backend/app/services/reminder_service.py`

- [ ] **Step 1: 给 ReminderService 添加缓存**

修改 `backend/app/services/reminder_service.py`，在写操作后调用 `invalidate_user_reminders`：

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_reminders
from app.models import ReminderJob, ReminderStatus
from app.models.enums import ReminderTargetType
from app.services.channel_identity_service import ChannelIdentityService

_REMINDERS_TTL = 600  # 10 分钟


class ReminderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.channel_identities = ChannelIdentityService(db)

    def create_for_target(
        self,
        *,
        user_id: str,
        target_type: str,
        target_id: str,
        title: str,
        trigger_time: datetime,
        conversation_id: str | None = None,
    ) -> ReminderJob:
        job = ReminderJob(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            title=title,
            conversation_id=conversation_id or self.channel_identities.get_conversation_id(user_id),
            trigger_time=trigger_time,
            status=ReminderStatus.PENDING.value,
        )
        self.db.add(job)
        self.db.flush()
        invalidate_user_reminders(user_id)
        return job

    def create_from_scheduled_item(
        self,
        user_id: str,
        scheduled_item_id: str,
        title: str,
        trigger_time: datetime,
        remind_before_minutes: int,
        conversation_id: str | None = None,
    ) -> ReminderJob:
        actual_trigger = trigger_time - timedelta(minutes=remind_before_minutes)
        reminder = ReminderJob(
            user_id=user_id,
            target_type=ReminderTargetType.SCHEDULED_ITEM.value,
            target_id=scheduled_item_id,
            title=title,
            trigger_time=actual_trigger,
            conversation_id=conversation_id or self.channel_identities.get_conversation_id(user_id),
            status=ReminderStatus.PENDING.value,
        )
        self.db.add(reminder)
        self.db.flush()
        invalidate_user_reminders(user_id)
        return reminder

    def cancel_by_target(self, *, user_id: str, target_id: str) -> None:
        stmt = select(ReminderJob).where(
            ReminderJob.user_id == user_id,
            ReminderJob.target_id == target_id,
            ReminderJob.status == ReminderStatus.PENDING.value,
        )
        for job in self.db.scalars(stmt):
            job.status = ReminderStatus.CANCELED.value
        invalidate_user_reminders(user_id)

    def list_jobs(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReminderJob], int]:
        base = select(ReminderJob).where(ReminderJob.user_id == user_id)
        if status:
            base = base.where(ReminderJob.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            base = base.where(ReminderJob.title.ilike(pattern))
        total = self.db.scalar(select(func.count()).select_from(base.subquery()))
        items = list(
            self.db.scalars(
                base.order_by(ReminderJob.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def list_jobs_cached(self, user_id: str, status: str | None = None) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:reminders:status:{status or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items, _ = self.list_jobs(user_id, status=status, page_size=100)
        result = [
            {
                "id": item.id,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "title": item.title,
                "trigger_time": item.trigger_time.isoformat(),
                "status": item.status,
                "retry_count": item.retry_count,
                "max_retries": item.max_retries,
                "error_message": item.error_message,
                "fired_at": item.fired_at.isoformat() if item.fired_at else None,
                "conversation_id": item.conversation_id,
            }
            for item in items
        ]
        cache_set(cache_key, result, _REMINDERS_TTL)
        return result

    def get_job(self, user_id: str, job_id: str) -> ReminderJob | None:
        stmt = select(ReminderJob).where(ReminderJob.user_id == user_id, ReminderJob.id == job_id)
        return self.db.scalar(stmt)

    def cancel_job(self, job: ReminderJob) -> ReminderJob:
        job.status = ReminderStatus.CANCELED.value
        invalidate_user_reminders(job.user_id)
        return job

    def reactivate_job(self, job: ReminderJob, new_trigger_time: datetime | None = None) -> ReminderJob:
        job.status = ReminderStatus.PENDING.value
        job.retry_count = 0
        job.error_message = None
        if new_trigger_time:
            job.trigger_time = new_trigger_time
        invalidate_user_reminders(job.user_id)
        return job

    def fire_due_jobs(self, now: datetime | None = None) -> list[ReminderJob]:
        now = now or datetime.now(UTC)
        stmt = select(ReminderJob).where(
            ReminderJob.status == ReminderStatus.PENDING.value,
            ReminderJob.trigger_time <= now,
        )
        jobs = list(self.db.scalars(stmt))
        for job in jobs:
            job.status = ReminderStatus.FIRED.value
            job.fired_at = now
            invalidate_user_reminders(job.user_id)
        return jobs
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/reminder_service.py
git commit -m "feat(cache): ReminderService 接入 Redis 缓存"
```

---

## Task 10: 后端缓存接入 — ConflictService + 查询优化

**Files:**
- Modify: `backend/app/services/conflict_service.py`

- [ ] **Step 1: 给 ConflictService 添加缓存 + 优化 list_conflicts**

修改 `backend/app/services/conflict_service.py`：

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_user_conflicts
from app.models import ConflictSeverity, ConflictStatus, ConflictType, ScheduleConflict
from app.models.enums import ScheduledItemStatus
from app.models.scheduled_item import ScheduledItem

_CONFLICTS_TTL = 600  # 10 分钟


class ConflictService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _item_has_finished(self, item: ScheduledItem, now: datetime) -> bool:
        return self._as_utc(item.end_time) <= now  # noqa: SIM300

    def _pair_key(self, related_item_ids: dict[str, Any] | None) -> tuple[str, str] | None:
        if not isinstance(related_item_ids, dict):
            return None
        current = related_item_ids.get("current")
        other = related_item_ids.get("other")
        if not isinstance(current, str) or not isinstance(other, str):
            return None
        first, second = sorted((current, other))
        return first, second

    def _has_open_conflict(
        self,
        *,
        user_id: str,
        conflict_type: str,
        related_item_ids: dict[str, Any],
    ) -> bool:
        target_pair = self._pair_key(related_item_ids)
        if target_pair is None:
            return False
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.conflict_type == conflict_type,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        for conflict in self.db.scalars(stmt):
            if self._pair_key(conflict.related_item_ids) == target_pair:
                return True
        return False

    def _has_active_related_items(
        self,
        user_id: str,
        related_item_ids: dict[str, Any] | None,
        *,
        now: datetime,
    ) -> bool:
        target_pair = self._pair_key(related_item_ids)
        if target_pair is None:
            return True
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
            ScheduledItem.id.in_(target_pair),
        )
        related_items = list(self.db.scalars(stmt))
        if len(related_items) != len(target_pair):
            return False
        return any(not self._item_has_finished(item, now) for item in related_items)

    def _resolve_stale_open_conflicts(self, user_id: str, now: datetime) -> None:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        changed = False
        for conflict in self.db.scalars(stmt):
            if self._has_active_related_items(
                user_id,
                conflict.related_item_ids,
                now=now,
            ):
                continue
            conflict.status = ConflictStatus.RESOLVED.value
            conflict.resolved_at = now
            changed = True
        if changed:
            self.db.flush()
            invalidate_user_conflicts(user_id)

    def _item_sort_key(self, item: ScheduledItem) -> tuple[str, str, str]:
        return (item.start_time.isoformat(), item.end_time.isoformat(), item.id)

    def _ordered_pair(
        self, first: ScheduledItem, second: ScheduledItem
    ) -> tuple[ScheduledItem, ScheduledItem]:
        first_key = self._item_sort_key(first)
        second_key = self._item_sort_key(second)
        if second_key < first_key:
            return second, first
        return first, second

    def detect_item_conflicts(
        self, user_id: str, item: ScheduledItem
    ) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = select(ScheduledItem).where(
            ScheduledItem.user_id == user_id,
            ScheduledItem.status == "active",
            ScheduledItem.id != item.id,
            ScheduledItem.start_time < item.end_time,
            ScheduledItem.end_time > item.start_time,
        )
        conflicts: list[ScheduleConflict] = []
        for other in self.db.scalars(stmt):
            primary, secondary = self._ordered_pair(item, other)
            related_item_ids = {"current": primary.id, "other": secondary.id}
            if self._has_open_conflict(
                user_id=user_id,
                conflict_type=ConflictType.TIME_OVERLAP.value,
                related_item_ids=related_item_ids,
            ):
                continue
            conflict = ScheduleConflict(
                user_id=user_id,
                conflict_type=ConflictType.TIME_OVERLAP.value,
                severity=ConflictSeverity.HIGH.value,
                title=f"安排冲突：{primary.title} 与 {secondary.title}",
                description=f"{primary.title} 与 {secondary.title} 的时间存在重叠。",
                related_item_ids=related_item_ids,
                suggestion="请调整其中一个安排时间，或选择忽略冲突。",
                status=ConflictStatus.OPEN.value,
                detected_at=datetime.now(UTC),
            )
            self.db.add(conflict)
            conflicts.append(conflict)
        self.db.flush()
        if conflicts:
            invalidate_user_conflicts(user_id)
        return conflicts

    def detect_day_conflicts(self, user_id: str) -> list[ScheduleConflict]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = (
            select(ScheduledItem)
            .where(
                ScheduledItem.user_id == user_id,
                ScheduledItem.status == "active",
            )
            .order_by(ScheduledItem.start_time.asc())
        )
        items = list(self.db.scalars(stmt))
        conflicts: list[ScheduleConflict] = []
        for index, item in enumerate(items):
            for other in items[index + 1 :]:
                if other.start_time >= item.end_time:
                    break
                primary, secondary = self._ordered_pair(item, other)
                related_item_ids = {"current": primary.id, "other": secondary.id}
                if self._has_open_conflict(
                    user_id=user_id,
                    conflict_type=ConflictType.TIME_OVERLAP.value,
                    related_item_ids=related_item_ids,
                ):
                    continue
                conflict = ScheduleConflict(
                    user_id=user_id,
                    conflict_type=ConflictType.TIME_OVERLAP.value,
                    severity=ConflictSeverity.HIGH.value,
                    title=f"安排冲突：{primary.title} 与 {secondary.title}",
                    description="存在时间重叠。",
                    related_item_ids=related_item_ids,
                    suggestion="请调整其中一个安排时间，或选择忽略冲突。",
                    status=ConflictStatus.OPEN.value,
                    detected_at=now,
                )
                self.db.add(conflict)
                conflicts.append(conflict)
        self.db.flush()
        if conflicts:
            invalidate_user_conflicts(user_id)
        return conflicts

    def list_conflicts(
        self,
        user_id: str,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScheduleConflict], int]:
        now = datetime.now(UTC)
        self._resolve_stale_open_conflicts(user_id, now)
        stmt = select(ScheduleConflict).where(ScheduleConflict.user_id == user_id)
        if status:
            stmt = stmt.where(ScheduleConflict.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                (ScheduleConflict.title.ilike(pattern)) | (ScheduleConflict.description.ilike(pattern))
            )
        conflicts = list(self.db.scalars(stmt.order_by(ScheduleConflict.created_at.desc())))
        seen: set[tuple[str, str, tuple[str, str] | None]] = set()
        unique_conflicts: list[ScheduleConflict] = []
        for conflict in conflicts:
            if conflict.status == ConflictStatus.OPEN.value:
                if not self._has_active_related_items(user_id, conflict.related_item_ids, now=now):
                    conflict.status = ConflictStatus.RESOLVED.value
                    conflict.resolved_at = now
                    continue
            pair_key = self._pair_key(conflict.related_item_ids)
            key = (conflict.conflict_type, conflict.status, pair_key)
            if key in seen:
                continue
            seen.add(key)
            unique_conflicts.append(conflict)
        total = len(unique_conflicts)
        start = (page - 1) * page_size
        return unique_conflicts[start : start + page_size], total

    def list_conflicts_cached(self, user_id: str, status: str | None = None) -> list[dict]:
        cache_key = f"schedule:user:{user_id}:conflicts:status:{status or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        items, _ = self.list_conflicts(user_id, status=status, page_size=100)
        result = [
            {
                "id": c.id,
                "conflict_type": c.conflict_type,
                "severity": c.severity,
                "title": c.title,
                "description": c.description,
                "related_item_ids": c.related_item_ids,
                "suggestion": c.suggestion,
                "status": c.status,
                "detected_at": c.detected_at.isoformat(),
                "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
            }
            for c in items
        ]
        cache_set(cache_key, result, _CONFLICTS_TTL)
        return result

    def resolve_conflicts_for_item(self, user_id: str, item_id: str) -> list[ScheduleConflict]:
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.status == ConflictStatus.OPEN.value,
        )
        resolved_conflicts: list[ScheduleConflict] = []
        for conflict in self.db.scalars(stmt):
            pair_key = self._pair_key(conflict.related_item_ids)
            if pair_key is None or item_id not in pair_key:
                continue
            conflict.status = ConflictStatus.RESOLVED.value
            conflict.resolved_at = datetime.now(UTC)
            resolved_conflicts.append(conflict)
        self.db.flush()
        if resolved_conflicts:
            invalidate_user_conflicts(user_id)
        return resolved_conflicts

    def get_conflict(self, user_id: str, conflict_id: str) -> ScheduleConflict | None:
        self._resolve_stale_open_conflicts(user_id, datetime.now(UTC))
        stmt = select(ScheduleConflict).where(
            ScheduleConflict.user_id == user_id,
            ScheduleConflict.id == conflict_id,
        )
        return self.db.scalar(stmt)

    def ignore_conflict(self, conflict: ScheduleConflict) -> ScheduleConflict:
        conflict.status = ConflictStatus.IGNORED.value
        invalidate_user_conflicts(conflict.user_id)
        return conflict

    def resolve_conflict(self, conflict: ScheduleConflict) -> ScheduleConflict:
        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolved_at = datetime.now(UTC)
        invalidate_user_conflicts(conflict.user_id)
        return conflict
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/conflict_service.py
git commit -m "feat(cache): ConflictService 接入 Redis 缓存 + 写操作失效"
```

---

## Task 11: 天气缓存迁移到 Redis

**Files:**
- Modify: `backend/app/services/daily_notification_service.py`

- [ ] **Step 1: 迁移天气缓存到 Redis**

修改 `backend/app/services/daily_notification_service.py`，移除内存 dict 缓存，改用 Redis：

```python
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.cache_invalidator import invalidate_weather
from app.core.config import get_settings
from app.models.enums import ScheduledItemStatus, TaskStatus
from app.models.schedule import TaskItem
from app.models.scheduled_item import ScheduledItem
from app.models.user import User, UserSettings

logger = logging.getLogger(__name__)

WEATHER_CACHE_TTL_SECONDS = 3600  # 1 小时


def _weather_cache_key(city: str) -> str:
    city_hash = hashlib.md5(city.encode()).hexdigest()[:12]
    return f"schedule:weather:{city_hash}"


class DailyNotificationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_due_users(self) -> list[User]:
        stmt = (
            select(User)
            .join(UserSettings)
            .where(UserSettings.daily_plan_push_enabled.is_(True))
        )
        users = list(self.db.scalars(stmt))
        current_time_utc = datetime.now(UTC)
        due_users: list[User] = []
        for user in users:
            settings = user.settings
            if settings is None:
                continue
            timezone_name = settings.default_timezone or "Asia/Shanghai"
            try:
                local_now = current_time_utc.astimezone(ZoneInfo(timezone_name))
            except Exception:
                local_now = current_time_utc.astimezone(ZoneInfo("Asia/Shanghai"))
            current_time = local_now.strftime("%H:%M")
            push_time = (settings.daily_plan_push_time or "08:00")[:5]
            if push_time == current_time:
                due_users.append(user)
        return due_users

    def notify_user(self, user: User) -> bool:
        from app.models.channel import ChannelIdentity
        from app.services.wechat_channel_service import WechatChannelService

        events = self._get_today_events(user.id)
        tasks = self._get_today_tasks(user.id)

        settings = self.db.scalar(
            select(UserSettings).where(UserSettings.user_id == user.id)
        )
        city = settings.city if settings else None
        weather = None
        if city:
            try:
                weather = self.get_weather(city)
            except Exception:
                logger.exception("获取天气失败: city=%s", city)

        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))
        except Exception:
            timezone_name = "Asia/Shanghai"
            local_now = datetime.now(UTC).astimezone(ZoneInfo(timezone_name))

        message = self.build_message(
            date=local_now,
            weather=weather,
            city=city,
            events=events,
            tasks=tasks,
        )

        identity = self.db.scalar(
            select(ChannelIdentity).where(
                ChannelIdentity.channel == "wechat",
                ChannelIdentity.user_id == user.id,
                ChannelIdentity.status == "active",
            )
        )
        if identity is None:
            logger.info("用户 %s 没有绑定微信，跳过推送", user.id)
            return False

        wechat_service = WechatChannelService(self.db)
        log = wechat_service.send_text(
            conversation_id=identity.conversation_id,
            content=message,
            user_id=user.id,
        )
        return log.status == "sent"

    def get_weather(self, city: str) -> dict[str, Any]:
        cache_key = _weather_cache_key(city)
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        data = self._fetch_weather_from_api(city)
        cache_set(cache_key, data, WEATHER_CACHE_TTL_SECONDS)
        return data

    def build_message(
        self,
        *,
        date: datetime,
        weather: dict[str, Any] | None,
        city: str | None,
        events: list[dict[str, str]],
        tasks: list[dict[str, str]],
    ) -> str:
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_names[date.weekday()]
        date_str = date.strftime("%Y-%m-%d")

        lines: list[str] = []
        lines.append(f"\U0001f324 早安！今天是 {date_str} {weekday}")
        lines.append("")

        if weather and city:
            icon = weather.get("icon", "\U0001f324")
            desc = weather.get("desc", "")
            temp = weather.get("temp", "?")
            lines.append(f"\U0001f4cd {city} 今日天气：{icon} {desc}  {temp}°C")
            lines.append("")
        elif city:
            lines.append(f"\U0001f4cd {city}")
            lines.append("")

        lines.append("\U0001f4c5 今日安排：")
        if events:
            for event in events:
                loc = f"  \U0001f4cd {event['location']}" if event.get("location") else ""
                lines.append(f"  • {event['time']} - {event['title']}{loc}")
        else:
            lines.append("  （暂无安排）")
        lines.append("")

        lines.append("✅ 待办任务：")
        if tasks:
            for task in tasks:
                priority = task.get("priority", "")
                prio_tag = f"（{priority}优先级）" if priority else ""
                lines.append(f"  • {task['title']}{prio_tag}")
        else:
            lines.append("  （暂无待办任务）")
        lines.append("")

        lines.append("\U0001f4cc 回复我可调整今日安排～")
        return "\n".join(lines)

    def _get_today_events(self, user_id: str) -> list[dict[str, str]]:
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(UTC).astimezone(local_tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        stmt = (
            select(ScheduledItem)
            .where(
                ScheduledItem.user_id == user_id,
                ScheduledItem.start_time >= start_of_day,
                ScheduledItem.start_time < end_of_day,
                ScheduledItem.status == ScheduledItemStatus.ACTIVE.value,
            )
            .order_by(ScheduledItem.start_time.asc())
        )
        results = []
        for item in self.db.scalars(stmt):
            results.append({
                "time": item.start_time.strftime("%H:%M"),
                "title": item.title,
                "location": item.location or "",
            })
        return results

    def _get_today_tasks(self, user_id: str) -> list[dict[str, str]]:
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        timezone_name = settings.default_timezone if settings else "Asia/Shanghai"
        try:
            local_tz = ZoneInfo(timezone_name)
        except Exception:
            local_tz = ZoneInfo("Asia/Shanghai")
        now = datetime.now(UTC).astimezone(local_tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        stmt = (
            select(TaskItem)
            .where(
                TaskItem.user_id == user_id,
                TaskItem.deadline >= start_of_day,
                TaskItem.deadline < end_of_day,
                TaskItem.status == TaskStatus.PENDING.value,
            )
            .order_by(TaskItem.priority.desc(), TaskItem.created_at.asc())
        )
        results = []
        for task in self.db.scalars(stmt):
            results.append({
                "title": task.title,
                "priority": task.priority,
            })
        return results

    def _fetch_weather_from_api(self, city: str) -> dict[str, Any]:
        settings = get_settings()
        api_key = settings.weather_api_key
        if not api_key:
            logger.warning("天气 API Key 未配置")
            return {"desc": "未知", "temp": "?", "icon": "\U0001f324"}

        provider = settings.weather_api_provider or "qweather"
        if provider == "qweather":
            return self._fetch_qweather(city, api_key)
        elif provider == "openweathermap":
            return self._fetch_openweathermap(city, api_key)
        else:
            return {"desc": "未知", "temp": "?", "icon": "\U0001f324"}

    def _fetch_qweather(self, city: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            geo = client.get(
                "https://geoapi.qweather.com/v2/city/lookup",
                params={"location": city, "key": api_key},
            )
            geo.raise_for_status()
            geo_data = geo.json()
            if geo_data.get("code") != "200" or not geo_data.get("location"):
                raise RuntimeError(f"找不到城市: {city}")
            loc_id = geo_data["location"][0]["id"]

            weather = client.get(
                "https://devapi.qweather.com/v7/weather/now",
                params={"location": loc_id, "key": api_key},
            )
            weather.raise_for_status()
            wdata = weather.json()
            if wdata.get("code") != "200":
                raise RuntimeError(f"天气查询失败: {wdata}")

            now_data = wdata.get("now", {})
            return {
                "desc": now_data.get("text", "未知"),
                "temp": now_data.get("temp", "?"),
                "icon": self._qweather_icon_to_emoji(now_data.get("icon", "")),
            }

    def _fetch_openweathermap(self, city: str, api_key: str) -> dict[str, Any]:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "appid": api_key, "units": "metric", "lang": "zh_cn"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "desc": data["weather"][0]["description"],
                "temp": round(data["main"]["temp"]),
                "icon": self._owm_icon_to_emoji(data["weather"][0]["icon"]),
            }

    @staticmethod
    def _qweather_icon_to_emoji(icon: str) -> str:
        mapping = {
            "100": "☀️", "101": "\U0001f324", "102": "⛅", "103": "\U0001f325",
            "104": "☁️", "150": "\U0001f319", "151": "\U0001f319",
            "300": "\U0001f326", "301": "\U0001f326", "302": "\U0001f327", "303": "\U0001f327",
            "400": "\U0001f328", "401": "\U0001f328", "402": "\U0001f328",
            "500": "\U0001f32b", "501": "\U0001f32b", "502": "\U0001f32b",
            "503": "\U0001f32a", "504": "\U0001f32a",
            "507": "\U0001f3d4", "508": "\U0001f3d4",
        }
        return mapping.get(icon, "\U0001f324")

    @staticmethod
    def _owm_icon_to_emoji(icon: str) -> str:
        mapping = {
            "01d": "☀️", "01n": "\U0001f319", "02d": "\U0001f324", "02n": "\U0001f319",
            "03d": "⛅", "03n": "☁️", "04d": "☁️", "04n": "☁️",
            "09d": "\U0001f327", "09n": "\U0001f327", "10d": "\U0001f326", "10n": "\U0001f327",
            "11d": "⛈", "11n": "⛈", "13d": "\U0001f328", "13n": "\U0001f328",
            "50d": "\U0001f32b", "50n": "\U0001f32b",
        }
        return mapping.get(icon, "\U0001f324")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/daily_notification_service.py
git commit -m "feat(cache): 天气缓存从内存 dict 迁移到 Redis"
```

---

## Task 12: 后端缓存接入 — PendingStateService

**Files:**
- Modify: `backend/app/services/pending_state_service.py`

- [ ] **Step 1: 给 PendingStateService 添加缓存**

修改 `backend/app/services/pending_state_service.py`：

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set, cache_delete
from app.core.cache_invalidator import invalidate_pending_state
from app.models import AgentPendingState, PendingStateStatus

_PENDING_STATE_TTL = 300  # 5 分钟


def _as_utc(datetime_value: datetime) -> datetime:
    if datetime_value.tzinfo is None:
        return datetime_value.replace(tzinfo=UTC)
    return datetime_value.astimezone(UTC)


class PendingStateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active(self, user_id: str, conversation_id: str) -> AgentPendingState | None:
        stmt = select(AgentPendingState).where(
            AgentPendingState.user_id == user_id,
            AgentPendingState.conversation_id == conversation_id,
            AgentPendingState.status == PendingStateStatus.ACTIVE.value,
        )
        state = self.db.scalar(stmt)
        if state and _as_utc(state.expires_at) < datetime.now(UTC):
            state.status = PendingStateStatus.EXPIRED.value
            invalidate_pending_state(conversation_id)
            return None
        return state

    def get_active_dict(self, user_id: str, conversation_id: str) -> dict | None:
        cache_key = f"schedule:agent:pending:{conversation_id}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        state = self.get_active(user_id, conversation_id)
        if state is None:
            return None
        result = {
            "id": state.id,
            "user_id": state.user_id,
            "conversation_id": state.conversation_id,
            "state_type": state.state_type,
            "state_payload": state.state_payload,
            "expires_at": state.expires_at.isoformat(),
            "status": state.status,
        }
        cache_set(cache_key, result, _PENDING_STATE_TTL)
        return result

    def save(
        self,
        *,
        user_id: str,
        conversation_id: str,
        state_type: str,
        state_payload: dict,
        expires_in_minutes: int = 60,
    ) -> AgentPendingState:
        current = self.get_active(user_id, conversation_id)
        if current:
            current.status = PendingStateStatus.CANCELED.value
        pending = AgentPendingState(
            user_id=user_id,
            conversation_id=conversation_id,
            state_type=state_type,
            state_payload=state_payload,
            expires_at=datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
            status=PendingStateStatus.ACTIVE.value,
        )
        self.db.add(pending)
        self.db.flush()
        invalidate_pending_state(conversation_id)
        return pending

    def clear(
        self, user_id: str, conversation_id: str, status: str = PendingStateStatus.CANCELED.value
    ) -> None:
        current = self.get_active(user_id, conversation_id)
        if current:
            current.status = status
            invalidate_pending_state(conversation_id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/pending_state_service.py
git commit -m "feat(cache): PendingStateService 接入 Redis 缓存"
```

---

## Task 13: Docker Compose 添加 Redis 服务

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 添加 Redis 服务和环境变量**

修改 `docker-compose.yml`：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    platform: linux/amd64
    container_name: schedule-agent-postgres
    environment:
      POSTGRES_DB: schedule_agent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5433:5432"
    volumes:
      - schedule_agent_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d schedule_agent"]
      interval: 5s
      timeout: 5s
      retries: 20

  redis:
    image: redis:7-alpine
    platform: linux/amd64
    container_name: schedule-agent-redis
    ports:
      - "6380:6379"
    volumes:
      - schedule_agent_redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 20

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
    platform: linux/amd64
    container_name: schedule-agent-backend
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@postgres:5432/schedule_agent
      REDIS_URL: redis://redis:6379/0
      CORS_ALLOW_ORIGINS: http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:3002,http://127.0.0.1:3001
      WECHAT_CHANNEL_BASE_URL: http://wechat-channel:18789
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      wechat-channel:
        condition: service_healthy
    ports:
      - "8000:8000"
    command: >
      sh -c "uv run alembic upgrade head
      && uv run python -m app.bootstrap
      && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"

  wechat-channel:
    build:
      context: ./backend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
    platform: linux/amd64
    container_name: schedule-agent-wechat-channel
    env_file:
      - ./backend/.env
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@postgres:5432/schedule_agent
      REDIS_URL: redis://redis:6379/0
      CORS_ALLOW_ORIGINS: http://localhost:3000,http://127.0.0.1:3000
      WECHAT_CHANNEL_BASE_URL: http://wechat-channel:18789
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "18789:18789"
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:18789/health').read()\"",
        ]
      interval: 5s
      timeout: 5s
      retries: 20
    command: >
      sh -c "uv run alembic upgrade head
      && uv run python -m app.wechat_channel_main"

  web:
    build:
      context: ./web
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
    platform: linux/amd64
    container_name: schedule-agent-web
    env_file:
      - ./web/.env
    depends_on:
      - backend
    ports:
      - "3000:3000"

volumes:
  schedule_agent_pgdata:
  schedule_agent_redis_data:
```

- [ ] **Step 2: 后端依赖添加 redis-py**

修改 `backend/pyproject.toml`，在 `dependencies` 中添加：

```
"redis>=5.0",
```

- [ ] **Step 3: 安装依赖**

Run: `cd backend && uv sync`
Expected: 安装成功

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml backend/pyproject.toml backend/uv.lock
git commit -m "feat(cache): Docker Compose 添加 Redis 服务，后端添加 redis-py 依赖"
```

---

## Task 14: 前端 SWR Hooks

**Files:**
- Create: `web/hooks/useScheduledItems.ts`
- Create: `web/hooks/useTasks.ts`
- Create: `web/hooks/useConflicts.ts`
- Create: `web/hooks/useReminders.ts`
- Modify: `web/package.json`

- [ ] **Step 1: 安装 SWR**

Run: `cd web && pnpm add swr`

- [ ] **Step 2: 创建 useScheduledItems hook**

创建 `web/hooks/useScheduledItems.ts`：

```typescript
"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadScheduledItems, type ScheduledItem } from "@/lib/dashboard";

export function useScheduledItems(params: {
  date?: string;
  start_time?: string;
  end_time?: string;
  keyword?: string;
  status?: string;
}) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken
    ? ["scheduled-items", params.date, params.start_time, params.end_time, params.keyword, params.status]
    : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadScheduledItems(params, accessToken),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    },
  );

  return {
    items: data ?? [],
    isLoading,
    error,
    refresh: () => mutate(),
  };
}
```

- [ ] **Step 3: 创建 useTasks hook**

创建 `web/hooks/useTasks.ts`：

```typescript
"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadTasks, type TaskItem } from "@/lib/dashboard";

export function useTasks(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["tasks", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadTasks(status, accessToken),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    },
  );

  return {
    items: data ?? [],
    isLoading,
    error,
    refresh: () => mutate(),
  };
}
```

- [ ] **Step 4: 创建 useConflicts hook**

创建 `web/hooks/useConflicts.ts`：

```typescript
"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadConflicts, type ConflictItem } from "@/lib/dashboard";

export function useConflicts(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["conflicts", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadConflicts(status, accessToken),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    },
  );

  return {
    items: data ?? [],
    isLoading,
    error,
    refresh: () => mutate(),
  };
}
```

- [ ] **Step 5: 创建 useReminders hook**

创建 `web/hooks/useReminders.ts`：

```typescript
"use client";

import useSWR from "swr";
import { useAuth } from "@/components/auth-provider";
import { loadReminders, type ReminderItem } from "@/lib/dashboard";

export function useReminders(status?: string) {
  const { session } = useAuth();
  const accessToken = session?.accessToken;

  const key = accessToken ? ["reminders", status] : null;

  const { data, error, isLoading, mutate } = useSWR(
    key,
    () => loadReminders(status, accessToken),
    {
      revalidateOnFocus: false,
      dedupingInterval: 5000,
    },
  );

  return {
    items: data ?? [],
    isLoading,
    error,
    refresh: () => mutate(),
  };
}
```

- [ ] **Step 6: Commit**

```bash
git add web/hooks/useScheduledItems.ts web/hooks/useTasks.ts web/hooks/useConflicts.ts web/hooks/useReminders.ts web/package.json web/pnpm-lock.yaml
git commit -m "feat(web): 添加 SWR hooks 用于数据缓存和请求去重"
```

---

## Task 15: 前端 Dashboard 页面改造

**Files:**
- Modify: `web/app/dashboard/today/page.tsx`

- [ ] **Step 1: 改造 TodayPage 使用 SWR hooks**

修改 `web/app/dashboard/today/page.tsx`，将 `loadTodayDashboard` 替换为 SWR hooks。主要改动：

1. 导入新的 SWR hooks
2. 替换 `fetchData` 逻辑为 SWR
3. 保留 `fetchData` 作为 `mutate` 的包装

```typescript
import { useScheduledItems } from "@/hooks/useScheduledItems";
import { useTasks } from "@/hooks/useTasks";
import { useConflicts } from "@/hooks/useConflicts";
import { useReminders } from "@/hooks/useReminders";
```

在 `TodayPage` 组件中：

```typescript
const { items: events, isLoading: eventsLoading, refresh: refreshEvents } = useScheduledItems({ date: planDate });
const { items: tasks, isLoading: tasksLoading, refresh: refreshTasks } = useTasks();
const { items: conflicts, isLoading: conflictsLoading, refresh: refreshConflicts } = useConflicts("open");
const { items: reminders, isLoading: remindersLoading, refresh: refreshReminders } = useReminders("pending");

const loading = eventsLoading || tasksLoading || conflictsLoading || remindersLoading;

const viewData: TodayDashboardData = {
  events,
  tasks,
  conflicts,
  reminders,
};

const refreshData = useCallback(() => {
  refreshEvents();
  refreshTasks();
  refreshConflicts();
  refreshReminders();
}, [refreshEvents, refreshTasks, refreshConflicts, refreshReminders]);
```

移除原来的 `fetchData`、`data` state、`error` state（SWR 自带 error 处理）。

- [ ] **Step 2: 验证前端构建**

Run: `cd web && pnpm build`
Expected: 构建成功

- [ ] **Step 3: Commit**

```bash
git add web/app/dashboard/today/page.tsx
git commit -m "feat(web): Dashboard 今日页改用 SWR hooks 加载数据"
```

---

## Task 16: Docker 构建验证

- [ ] **Step 1: Docker 构建**

Run: `docker compose build --no-cache`
Expected: 所有镜像构建成功

- [ ] **Step 2: 启动服务**

Run: `docker compose up -d`
Expected: 所有服务启动成功

- [ ] **Step 3: 验证后端健康**

Run: `curl http://localhost:8000/health`
Expected: 返回 ok

- [ ] **Step 4: 验证 Redis 连接**

Run: `docker compose logs backend | grep -i redis`
Expected: 看到 "Redis 连接成功" 日志

- [ ] **Step 5: 验证前端**

访问 `http://localhost:3000`，检查今日页加载是否正常。

- [ ] **Step 6: 检查 Redis 缓存命中**

Run: `docker compose exec redis redis-cli keys "schedule:*"`
Expected: 看到缓存的 key

- [ ] **Step 7: 停止服务**

Run: `docker compose down`
