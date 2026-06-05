from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes.agent import run_agent_message
from app.models import User
from app.schemas.agent import DebugMessageRequest, DebugMessageResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/me/agent", tags=["agent"])


@router.post("/message")
def send_agent_message(
    payload: DebugMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[DebugMessageResponse]:
    response = run_agent_message(
        db=db,
        current_user=current_user,
        message=payload.message,
        conversation_id=f"web:{current_user.id}",
        channel="web",
    )
    return ApiResponse(data=response, message=response.final_response)
