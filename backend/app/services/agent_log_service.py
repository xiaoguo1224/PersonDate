from __future__ import annotations

import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models import AgentRunLog

logger = logging.getLogger(__name__)


class AgentLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_log(self, **data: object) -> AgentRunLog:
        logger.info("Agent 日志 user_id=%s intent=%s success=%s", data.get("user_id"), data.get("intent"), data.get("success"))
        encoded = {key: jsonable_encoder(value) for key, value in data.items()}
        log = AgentRunLog(**encoded)
        self.db.add(log)
        self.db.flush()
        return log
