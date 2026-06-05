from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph
from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.agent import DebugMessageRequest, DebugMessageResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/agent", tags=["agent"])


def run_agent_message(
    *,
    db: Session,
    current_user: User,
    message: str,
    conversation_id: str,
    channel: str,
) -> DebugMessageResponse:
    graph = SchedulePlanningGraph(db)
    state = graph.invoke(
        current_user=current_user,
        message=message,
        conversation_id=conversation_id,
        channel=channel,
    )
    db.commit()
    return DebugMessageResponse(
        success=state.success,
        final_response=state.final_response,
        intent=state.intent,
        tool_calls=state.tool_calls,
        tool_results=state.tool_results,
        pending_state=state.pending_state,
        graph_trace=state.graph_trace,
        error=state.error,
    )


@router.post("/debug/message")
def debug_message(
    payload: DebugMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DebugMessageResponse]:
    response = run_agent_message(
        db=db,
        current_user=current_user,
        message=payload.message,
        conversation_id="debug",
        channel="web",
    )
    return ApiResponse(data=response, message=response.final_response)
