from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChannelIdentity


class ChannelIdentityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_wechat_identity(self, user_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.user_id == user_id,
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.status == "active",
        ).order_by(ChannelIdentity.created_at.desc())
        return self.db.scalar(stmt)

    def get_conversation_id(self, user_id: str) -> str:
        identity = self.get_active_wechat_identity(user_id)
        return identity.conversation_id if identity else user_id

    def list_identities(self, user_id: str) -> list[ChannelIdentity]:
        stmt = select(ChannelIdentity).where(ChannelIdentity.user_id == user_id)
        return list(self.db.scalars(stmt.order_by(ChannelIdentity.created_at.desc())))
