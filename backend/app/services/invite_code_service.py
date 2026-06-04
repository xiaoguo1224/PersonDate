from datetime import UTC, datetime
from secrets import choice
from string import ascii_uppercase, digits

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InviteCode, InviteCodeStatus, InviteCodeUsage, User
from app.schemas.invite_code import InviteCodeCreateRequest

CODE_ALPHABET = ascii_uppercase + digits


class InviteCodeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_code(self, length: int = 8) -> str:
        while True:
            code = "-".join("".join(choice(CODE_ALPHABET) for _ in range(part)) for part in (4, 4))
            if self.db.scalar(select(InviteCode.id).where(InviteCode.code == code)) is None:
                return code

    def create(self, creator: User, payload: InviteCodeCreateRequest) -> InviteCode:
        invite_code = InviteCode(
            code=self.generate_code(),
            created_by_user_id=creator.id,
            max_uses=payload.max_uses,
            expires_at=payload.expires_at,
            remark=payload.remark,
        )
        self.db.add(invite_code)
        self.db.flush()
        return invite_code

    def list_all(self) -> list[InviteCode]:
        stmt = select(InviteCode).order_by(InviteCode.created_at.desc())
        return list(self.db.scalars(stmt))

    def disable(self, invite_code: InviteCode) -> InviteCode:
        invite_code.status = InviteCodeStatus.DISABLED.value
        return invite_code

    def validate(self, code: str) -> InviteCode:
        invite_code = self.db.scalar(select(InviteCode).where(InviteCode.code == code))
        if invite_code is None:
            raise ValueError("邀请码无效")
        if invite_code.status != InviteCodeStatus.ACTIVE.value:
            raise ValueError("邀请码已失效")
        if invite_code.expires_at and invite_code.expires_at < datetime.now(UTC):
            invite_code.status = InviteCodeStatus.EXPIRED.value
            raise ValueError("邀请码已过期")
        if invite_code.used_count >= invite_code.max_uses:
            raise ValueError("邀请码已被使用完")
        return invite_code

    def mark_used(self, invite_code: InviteCode, user: User) -> InviteCodeUsage:
        invite_code.used_count += 1
        usage = InviteCodeUsage(
            invite_code_id=invite_code.id,
            used_by_user_id=user.id,
            used_at=datetime.now(UTC),
        )
        self.db.add(usage)
        return usage
