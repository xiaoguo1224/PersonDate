from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import CalendarEvent, User
from app.schemas.common import ApiResponse
from app.schemas.schedule import (
    CalendarEventCreateRequest,
    CalendarEventItem,
    CalendarEventListResponse,
    CalendarEventUpdateRequest,
    SearchEventCandidateItem,
    SearchEventCandidatesResponse,
)
from app.services.calendar_event_service import CalendarEventService

router = APIRouter(prefix="/calendar-events", tags=["calendar-events"])


def _to_item(event: CalendarEvent) -> CalendarEventItem:
    return CalendarEventItem(
        id=event.id,
        title=event.title,
        description=event.description,
        start_time=event.start_time,
        end_time=event.end_time,
        timezone=event.timezone,
        location=event.location,
        status=event.status,
        remind_before_minutes=event.remind_before_minutes,
    )


@router.get("")
def list_calendar_events(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[CalendarEventListResponse]:
    timezone_name = (
        current_user.settings.default_timezone if current_user.settings else "Asia/Shanghai"
    )
    items = [
        _to_item(event)
        for event in CalendarEventService(db).list_events(
            current_user.id,
            start_date=start_date,
            end_date=end_date,
            timezone_name=timezone_name,
        )
    ]
    return ApiResponse(data=CalendarEventListResponse(items=items))


@router.post("")
def create_calendar_event(
    payload: CalendarEventCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[CalendarEventItem]:
    service = CalendarEventService(db)
    event = service.create_event(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone_name=payload.timezone,
        location=payload.location,
        remind_before_minutes=payload.remind_before_minutes,
        created_by_channel="web",
    )
    db.commit()
    return ApiResponse(data=_to_item(event), message="日程已创建")


@router.patch("/{event_id}")
def update_calendar_event(
    event_id: str,
    payload: CalendarEventUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[CalendarEventItem]:
    service = CalendarEventService(db)
    event = service.get_event(current_user.id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日程不存在")
    event = service.update_event(
        event,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone=payload.timezone,
        location=payload.location,
        remind_before_minutes=payload.remind_before_minutes,
    )
    db.commit()
    return ApiResponse(data=_to_item(event), message="日程已更新")


@router.delete("/{event_id}")
def delete_calendar_event(
    event_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, str]]:
    service = CalendarEventService(db)
    event = service.get_event(current_user.id, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日程不存在")
    service.delete_event(event)
    db.commit()
    return ApiResponse(data={"id": event.id}, message="日程已删除")


@router.get("/search")
def search_calendar_events(
    keyword: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: date | None = None,
) -> ApiResponse[SearchEventCandidatesResponse]:
    service = CalendarEventService(db)
    timezone_name = (
        current_user.settings.default_timezone if current_user.settings else "Asia/Shanghai"
    )
    items = [
        SearchEventCandidateItem(
            id=event.id,
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            timezone=event.timezone,
        )
        for event in service.search_candidates(current_user.id, keyword, date, timezone_name)
    ]
    return ApiResponse(data=SearchEventCandidatesResponse(items=items))
