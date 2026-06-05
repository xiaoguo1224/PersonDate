from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_owner
from app.models import AgentRunLog, User
from app.schemas.agent_log import AgentLogItem, AgentLogListResponse
from app.schemas.common import ApiResponse

router = APIRouter(tags=["agent-logs"])


def _to_item(log: AgentRunLog) -> AgentLogItem:
    return AgentLogItem(
        id=log.id,
        user_id=log.user_id,
        channel=log.channel,
        conversation_id=log.conversation_id,
        input_text=log.input_text,
        intent=log.intent,
        graph_trace=list(log.graph_trace or []),
        tools_called=list(log.tools_called or []),
        tool_results=list(log.tool_results or []),
        final_response=log.final_response,
        success=log.success,
        error_message=log.error_message,
        created_at=log.created_at,
    )


def _list_logs(db: Session, user_id: str | None) -> list[AgentRunLog]:
    stmt = select(AgentRunLog).order_by(AgentRunLog.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(AgentRunLog.user_id == user_id)
    return list(db.scalars(stmt.limit(50)))


@router.get("/my-agent-logs")
def list_my_agent_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AgentLogListResponse]:
    items = [_to_item(log) for log in _list_logs(db, current_user.id)]
    return ApiResponse(data=AgentLogListResponse(items=items))


@router.get("/admin/agent-logs")
def list_admin_agent_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
) -> ApiResponse[AgentLogListResponse]:
    items = [_to_item(log) for log in _list_logs(db, None)]
    return ApiResponse(data=AgentLogListResponse(items=items))
