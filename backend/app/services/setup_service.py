import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)
from app.models import User, UserRole, UserStatus
from app.schemas.setup import OwnerInitRequest
from app.services.user_service import UserService


class SetupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserService(db)

    def is_initialized(self) -> bool:
        owner_id = self.db.scalar(
            select(User.id).where(
                User.role == UserRole.OWNER.value,
                User.status != UserStatus.DELETED.value,
            )
        )
        return owner_id is not None

    def create_owner(self, payload: OwnerInitRequest) -> User:
        if self.is_initialized():
            logger.warning("初始化失败: 系统已经初始化")
            raise ValueError("系统已经初始化")
        settings = get_settings()
        owner = self.users.create_user(
            username="admin",
            password=settings.admin_password,
            role=UserRole.OWNER.value,
            display_name=payload.display_name,
            email=str(payload.email) if payload.email else None,
        )
        logger.info("系统初始化完成 owner_id=%s", owner.id)
        return owner
