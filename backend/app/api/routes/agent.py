from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.graph import SchedulePlanningGraph, build_agent_error_message, get_result_value
from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.agent import DebugMessageRequest, DebugMessageResponse
from app.schemas.common import ApiResponse
from app.services.agent_log_service import AgentLogService

router = APIRouter(prefix="/agent", tags=["agent"])


def run_agent_message(
    *,
    db: Session,
    current_user: User,
    message: str,
    conversation_id: str,
    channel: str,
) -> DebugMessageResponse:
    try:
        graph = SchedulePlanningGraph(db)
        result = graph.invoke(
            current_user=current_user,
            message=message,
            conversation_id=conversation_id,
            channel=channel,
        )
    except Exception as exc:
        error_message = build_agent_error_message(exc)
        AgentLogService(db).create_log(
            user_id=current_user.id,
            channel=channel,
            conversation_id=conversation_id,
            input_text=message,
            intent="",
            graph_trace=["agent_loop", "invoke_failed"],
            tools_called=[],
            tool_args=[],
            tool_results=[],
            final_response=error_message,
            success=False,
            error_message=error_message,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_message,
        ) from exc
    db.commit()
    return DebugMessageResponse(
        success=get_result_value(result, "success", True),
        final_response=get_result_value(result, "final_response", ""),
        intent=get_result_value(result, "intent", ""),
        tool_calls=get_result_value(result, "tool_calls", []),
        tool_results=get_result_value(result, "tool_results", []),
        graph_trace=get_result_value(result, "graph_trace", []),
        error=get_result_value(result, "error"),
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
