from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User, UserSettings, UserStatus


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
        settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
        if settings:
            return settings
        settings = UserSettings(user_id=user_id)
        self.db.add(settings)
        self.db.flush()
        return settings

    def mark_login(self, user: User) -> None:
        user.last_login_at = datetime.now(UTC)

    def disable_user(self, user: User) -> User:
        user.status = UserStatus.DISABLED.value
        return user

    def enable_user(self, user: User) -> User:
        user.status = UserStatus.ACTIVE.value
        return user
