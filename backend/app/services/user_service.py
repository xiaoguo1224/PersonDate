import logging
from datetime import UTC, datetime

from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserSettings, UserStatus
from app.schemas.user_settings import UpdateUserSettingsRequest


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
        logger.info("创建用户 user_id=%s username=%s role=%s", user.id, username, role)
        self.ensure_settings(user.id)
        return user

    def ensure_settings(self, user_id: str) -> UserSettings:
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        if settings:
            return settings
        settings = UserSettings(user_id=user_id)
        self.db.add(settings)
        self.db.flush()
        logger.info("创建用户配置 user_id=%s", user_id)
        return settings

    def mark_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        logger.info("用户登录 user_id=%s username=%s", user.id, user.username)

    def disable_user(self, user: User) -> User:
        user.status = UserStatus.DISABLED.value
        logger.info("禁用用户 user_id=%s username=%s", user.id, user.username)
        return user

    def enable_user(self, user: User) -> User:
        user.status = UserStatus.ACTIVE.value
        logger.info("启用用户 user_id=%s username=%s", user.id, user.username)
        return user

    def update_settings(self, user_id: str, payload: UpdateUserSettingsRequest) -> UserSettings:
        settings = self.ensure_settings(user_id)
        changed_fields: list[str] = []
        if payload.default_timezone is not None:
            settings.default_timezone = payload.default_timezone
            changed_fields.append("default_timezone")
        if payload.workday_start_time is not None:
            settings.workday_start_time = payload.workday_start_time
            changed_fields.append("workday_start_time")
        if payload.workday_end_time is not None:
            settings.workday_end_time = payload.workday_end_time
            changed_fields.append("workday_end_time")
        if payload.daily_plan_push_time is not None:
            settings.daily_plan_push_time = payload.daily_plan_push_time
            changed_fields.append("daily_plan_push_time")
        if payload.default_remind_before_minutes is not None:
            settings.default_remind_before_minutes = payload.default_remind_before_minutes
            changed_fields.append("default_remind_before_minutes")
        if payload.daily_plan_push_enabled is not None:
            settings.daily_plan_push_enabled = payload.daily_plan_push_enabled
            changed_fields.append("daily_plan_push_enabled")
        logger.info("更新用户配置 user_id=%s 字段=%s", user_id, ",".join(changed_fields))
        return settings
