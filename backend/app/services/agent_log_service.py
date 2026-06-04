from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models import AgentRunLog


class AgentLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_log(self, **data: object) -> AgentRunLog:
        encoded = {key: jsonable_encoder(value) for key, value in data.items()}
        log = AgentRunLog(**encoded)
        self.db.add(log)
        self.db.flush()
        return log
