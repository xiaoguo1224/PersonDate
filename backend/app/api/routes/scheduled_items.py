from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import ApiResponse
from app.schemas.scheduled_item import (
    ConfirmDayDraftsRequest,
    GenerateDayDraftsRequest,
    ScheduledItemCreateRequest,
    ScheduledItemDTO,
    ScheduledItemListResponse,
    ScheduledItemUpdateRequest,
)
from app.services.conflict_service import ConflictService
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService

router = APIRouter(prefix="/scheduled-items", tags=["scheduled_items"])


def _to_dto(item: object) -> ScheduledItemDTO:
    return ScheduledItemDTO(
        id=item.id,
        title=item.title,
        description=item.description,
        start_time=item.start_time,
        end_time=item.end_time,
        timezone=item.timezone,
        location=item.location,
        source=item.source,
        source_task_id=item.source_task_id,
        remind_before_minutes=item.remind_before_minutes,
        status=item.status,
        sort_order=item.sort_order,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("", response_model=ApiResponse[ScheduledItemDTO])
def create_scheduled_item(
    payload: ScheduledItemCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.create(
        user_id=current_user.id,
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone=payload.timezone,
        description=payload.description,
        location=payload.location,
        source=payload.source,
        source_task_id=payload.source_task_id,
        remind_before_minutes=payload.remind_before_minutes,
    )

    # 检测冲突
    conflict_service = ConflictService(db)
    conflicts = conflict_service.detect_item_conflicts(current_user.id, item)

    # 如果有冲突，尝试调整弹性任务
    if conflicts:
        task_service = TaskService(db)
        for conflict in conflicts:
            related_ids = conflict.related_item_ids
            if not related_ids:
                continue
            # 检查冲突的另一项是否是弹性任务
            other_id = related_ids.get("other") if related_ids.get("current") == item.id else related_ids.get("current")
            if other_id:
                other_item = service.get(current_user.id, other_id)
                if other_item and other_item.source_task_id:
                    task = task_service.get_task(current_user.id, other_item.source_task_id)
                    if task and task.time_type == "flexible":
                        # 尝试重新安排弹性任务
                        task_service.reschedule_conflicted_item(current_user.id, task, other_item)

    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已创建")


@router.get("", response_model=ApiResponse[ScheduledItemListResponse])
def list_scheduled_items(
    db: DbSession,
    current_user: CurrentUser,
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    date: date | None = Query(None),
    keyword: str | None = Query(None),
    status: str | None = Query(None),
) -> ApiResponse[ScheduledItemListResponse]:
    service = ScheduledItemService(db)

    if keyword:
        items = service.search(current_user.id, keyword, date)
    elif date:
        items = service.list_by_date(current_user.id, date)
    elif start_time and end_time:
        items = service.list_by_date_range(current_user.id, start_time, end_time, status)
    else:
        items = []

    return ApiResponse(
        data=ScheduledItemListResponse(items=[_to_dto(item) for item in items]),
        message="安排查询完成",
    )


@router.get("/{item_id}", response_model=ApiResponse[ScheduledItemDTO])
def get_scheduled_item(
    item_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    return ApiResponse(data=_to_dto(item))


@router.patch("/{item_id}", response_model=ApiResponse[ScheduledItemDTO])
def update_scheduled_item(
    item_id: str,
    payload: ScheduledItemUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    item = service.update(
        item,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        timezone=payload.timezone,
        location=payload.location,
        remind_before_minutes=payload.remind_before_minutes,
        status=payload.status,
    )
    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已更新")


@router.delete("/{item_id}", response_model=ApiResponse)
def delete_scheduled_item(
    item_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    service.soft_delete(item)
    db.commit()
    return ApiResponse(message="安排已删除")


@router.patch("/{item_id}/complete", response_model=ApiResponse[ScheduledItemDTO])
def complete_scheduled_item(
    item_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScheduledItemDTO]:
    service = ScheduledItemService(db)
    item = service.get(current_user.id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="安排不存在")
    item = service.mark_completed(item)
    db.commit()
    return ApiResponse(data=_to_dto(item), message="安排已完成")


@router.post("/generate/{plan_date}", response_model=ApiResponse[ScheduledItemListResponse])
def generate_day_drafts(
    plan_date: date,
    payload: GenerateDayDraftsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse[ScheduledItemListResponse]:
    service = ScheduledItemService(db)
    items = service.generate_day_drafts(
        user_id=current_user.id,
        plan_date=plan_date,
    )
    db.commit()
    return ApiResponse(
        data=ScheduledItemListResponse(items=[_to_dto(item) for item in items]),
        message="安排草案已生成",
    )


@router.post("/confirm", response_model=ApiResponse)
def confirm_day_drafts(
    payload: ConfirmDayDraftsRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ApiResponse:
    service = ScheduledItemService(db)
    count = service.confirm_drafts_for_date(current_user.id, payload.plan_date)
    db.commit()
    return ApiResponse(message=f"已确认 {count} 项安排")
