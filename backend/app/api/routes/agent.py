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
    result = graph.invoke(
        current_user=current_user,
        message=message,
        conversation_id=conversation_id,
        channel=channel,
    )
    db.commit()
    return DebugMessageResponse(
        success=result.get("success", True),
        final_response=result.get("final_response", ""),
        intent=result.get("intent", ""),
        tool_calls=result.get("tool_calls", []),
        tool_results=result.get("tool_results", []),
        pending_state=result.get("pending_state"),
        graph_trace=result.get("graph_trace", []),
        error=result.get("error"),
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
