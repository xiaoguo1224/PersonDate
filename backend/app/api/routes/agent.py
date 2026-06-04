from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph
from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.agent import DebugMessageRequest, DebugMessageResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/debug/message")
def debug_message(
    payload: DebugMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DebugMessageResponse]:
    graph = SchedulePlanningGraph(db)
    state = graph.invoke(
        current_user=current_user,
        message=payload.message,
        conversation_id="debug",
        channel="web",
    )
    db.commit()
    response = DebugMessageResponse(
        success=state.success,
        final_response=state.final_response,
        intent=state.intent,
        tool_calls=state.tool_calls,
        tool_results=state.tool_results,
        pending_state=state.pending_state,
        graph_trace=state.graph_trace,
        error=state.error,
    )
    return ApiResponse(data=response, message=state.final_response)
