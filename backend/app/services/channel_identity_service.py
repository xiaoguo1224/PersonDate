import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChannelIdentity

logger = logging.getLogger(__name__)


class ChannelIdentityService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_latest_wechat_identity(self, user_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.user_id == user_id,
            ChannelIdentity.channel == "wechat",
        ).order_by(ChannelIdentity.bound_at.desc().nullslast(), ChannelIdentity.created_at.desc())
        return self.db.scalar(stmt)

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

    def get_by_channel_user_id(self, channel_user_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.channel_user_id == channel_user_id,
        )
        return self.db.scalar(stmt)

    def get_by_conversation_id(self, conversation_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.conversation_id == conversation_id,
        )
        return self.db.scalar(stmt)

    def get_active_by_channel_user_id(self, channel_user_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.channel_user_id == channel_user_id,
            ChannelIdentity.status == "active",
        )
        return self.db.scalar(stmt)

    def get_active_by_conversation_id(self, conversation_id: str) -> ChannelIdentity | None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.conversation_id == conversation_id,
            ChannelIdentity.status == "active",
        )
        return self.db.scalar(stmt)

    def disable_other_active_identities(
        self,
        *,
        user_id: str,
        keep_identity_id: str | None = None,
    ) -> None:
        stmt = select(ChannelIdentity).where(
            ChannelIdentity.user_id == user_id,
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.status == "active",
        )
        if keep_identity_id is not None:
            stmt = stmt.where(ChannelIdentity.id != keep_identity_id)
        for identity in self.db.scalars(stmt):
            identity.status = "disabled"

    def upsert_wechat_identity(
        self,
        *,
        user_id: str,
        channel_user_id: str,
        conversation_id: str,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> ChannelIdentity:
        identity = self.get_by_channel_user_id(channel_user_id) or self.get_by_conversation_id(
            conversation_id
        )
        if identity is not None and identity.user_id != user_id:
            raise ValueError("该微信身份已绑定到其他用户")

        if identity is None:
            identity = ChannelIdentity(
                user_id=user_id,
                channel="wechat",
                channel_user_id=channel_user_id,
                conversation_id=conversation_id,
                display_name=display_name,
                avatar_url=avatar_url,
                status="active",
            )
            self.db.add(identity)
            logger.info("新建微信绑定 user_id=%s channel_user_id=%s conversation_id=%s", user_id, channel_user_id, conversation_id)
        else:
            self.disable_other_active_identities(user_id=user_id, keep_identity_id=identity.id)
            identity.user_id = user_id
            identity.channel = "wechat"
            identity.channel_user_id = channel_user_id
            identity.conversation_id = conversation_id
            identity.display_name = display_name
            identity.avatar_url = avatar_url
            identity.status = "active"
            logger.info("更新微信绑定 user_id=%s channel_user_id=%s identity_id=%s", user_id, channel_user_id, identity.id)
            return identity

        self.disable_other_active_identities(user_id=user_id, keep_identity_id=identity.id)
        return identity
