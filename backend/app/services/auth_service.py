
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models import User, UserRole
from app.schemas.auth import LoginRequest, RegisterWithInviteRequest
from app.services.invite_code_service import InviteCodeService
from app.services.user_service import UserService


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserService(db)
        self.invite_codes = InviteCodeService(db)

    def login(self, payload: LoginRequest) -> tuple[User, str]:
        user = self.users.get_by_username(payload.username)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise ValueError("用户名或密码错误")
        self.users.mark_login(user)
        token = create_access_token(
            subject=user.id,
            claims={"user_id": user.id, "role": user.role, "username": user.username},
        )
        return user, token

    def register_with_invite(self, payload: RegisterWithInviteRequest) -> tuple[User, str]:
        invite_code = self.invite_codes.validate(payload.invite_code)
        if self.users.get_by_username(payload.username) is not None:
            raise ValueError("用户名已存在")

        user = self.users.create_user(
            username=payload.username,
            password=payload.password,
            role=UserRole.MEMBER.value,
            display_name=payload.display_name,
            email=str(payload.email) if payload.email else None,
        )
        self.invite_codes.mark_used(invite_code, user)
        token = create_access_token(
            subject=user.id,
            claims={"user_id": user.id, "role": user.role, "username": user.username},
        )
        return user, token
