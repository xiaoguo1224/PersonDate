from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
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
        logger.info("保存 pending state user_id=%s conversation_id=%s type=%s", user_id, conversation_id, state_type)
        return pending

    def clear(
        self, user_id: str, conversation_id: str, status: str = PendingStateStatus.CANCELED.value
    ) -> None:
        current = self.get_active(user_id, conversation_id)
        if current:
            current.status = status
            invalidate_pending_state(conversation_id)
            logger.info("清除 pending state user_id=%s conversation_id=%s status=%s", user_id, conversation_id, status)

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
