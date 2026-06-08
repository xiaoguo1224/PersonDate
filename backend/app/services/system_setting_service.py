from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SystemSetting
from app.schemas.system_setting import UpdateSystemSettingsRequest


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
        self._seed_defaults()
        stmt = select(SystemSetting).order_by(SystemSetting.key.asc())
        return list(self.db.scalars(stmt))

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
