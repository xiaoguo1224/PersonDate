from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.models import AgentPendingState, PendingStateStatus


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
            return None
        return state

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
        logger.info("保存 pending state user_id=%s conversation_id=%s type=%s", user_id, conversation_id, state_type)
        return pending

    def clear(
        self, user_id: str, conversation_id: str, status: str = PendingStateStatus.CANCELED.value
    ) -> None:
        current = self.get_active(user_id, conversation_id)
        if current:
            current.status = status
            logger.info("清除 pending state user_id=%s conversation_id=%s status=%s", user_id, conversation_id, status)
