from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.schemas.common import ApiResponse
from app.schemas.setup import OwnerInitRequest
from app.services.setup_service import SetupService

router = APIRouter(tags=["setup"])


@router.get("/setup/status")
def setup_status(db: DbSession) -> ApiResponse[dict[str, bool]]:
    service = SetupService(db)
    return ApiResponse(data={"initialized": service.is_initialized()})


@router.post("/setup/owner")
def setup_owner(db: DbSession, payload: OwnerInitRequest) -> ApiResponse[dict[str, str]]:
    service = SetupService(db)
    try:
        owner = service.create_owner(payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ApiResponse(data={"user_id": owner.id}, message="owner 初始化成功")
