from datetime import UTC, date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import TaskItem, User
from app.schemas.common import ApiResponse
from app.schemas.scheduled_item import ScheduledItemDTO, ScheduledItemListResponse
from app.schemas.task import TaskCreateRequest, TaskItemDTO, TaskListResponse, TaskUpdateRequest
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService, _UNSET

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_item(task: TaskItem) -> TaskItemDTO:
    return TaskItemDTO(
        id=task.id,
        title=task.title,
        description=task.description,
        estimated_minutes=task.estimated_minutes,
        deadline=task.deadline,
        priority=task.priority,
        status=task.status,
        schedule_type=task.schedule_type,
        start_date=task.start_date,
        end_date=task.end_date,
        duration_days=task.duration_days,
        time_type=task.time_type,
        scheduled_time=task.scheduled_time,
        scheduled_end_time=task.scheduled_end_time,
        completed_days=task.completed_days or 0,
    )


def _si_to_dto(item) -> ScheduledItemDTO:
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


@router.get("")
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ApiResponse[TaskListResponse]:
    service = TaskService(db)
    tasks, total = service.list_tasks(current_user.id, status=status, page=page, page_size=page_size)
    items = [_to_item(task) for task in tasks]
    return ApiResponse(data=TaskListResponse(items=items, total=total, page=page, page_size=page_size))


@router.post("")
def create_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskItemDTO]:
    service = TaskService(db)
    task = service.create_task(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        estimated_minutes=payload.estimated_minutes,
        deadline=payload.deadline,
        priority=payload.priority,
        schedule_type=payload.schedule_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        duration_days=payload.duration_days,
        time_type=payload.time_type,
        scheduled_time=payload.scheduled_time,
        scheduled_end_time=payload.scheduled_end_time,
    )
    # 如果任务有排期配置，自动生成 ScheduledItem
    scheduled_items = []
    if task.schedule_type:
        scheduled_items = service.sync_task_to_scheduled_items(task, current_user.id)
    db.commit()
    msg = "任务已创建"
    if scheduled_items:
        msg = f"任务已创建，已生成 {len(scheduled_items)} 个排期"
    return ApiResponse(data=_to_item(task), message=msg)


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskItemDTO]:
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 排期相关字段：只要其中一个被显式传入（包括 null），就标记为变更
    SCHEDULE_FIELDS = (
        "schedule_type", "start_date", "end_date",
        "duration_days", "time_type", "scheduled_time",
        "scheduled_end_time", "estimated_minutes",
    )

    payload_dict = payload.model_dump(exclude_unset=True)
    schedule_changed = any(field in payload_dict for field in SCHEDULE_FIELDS)
    title_changed = "title" in payload_dict

    # 用 _UNSET 填充未传入的字段，使 update_task 能区分"未传入"和"传入 None"
    task = service.update_task(
        task,
        title=payload_dict.get("title", _UNSET),
        description=payload_dict.get("description", _UNSET),
        estimated_minutes=payload_dict.get("estimated_minutes", _UNSET),
        deadline=payload_dict.get("deadline", _UNSET),
        priority=payload_dict.get("priority", _UNSET),
        schedule_type=payload_dict.get("schedule_type", _UNSET),
        start_date=payload_dict.get("start_date", _UNSET),
        end_date=payload_dict.get("end_date", _UNSET),
        duration_days=payload_dict.get("duration_days", _UNSET),
        time_type=payload_dict.get("time_type", _UNSET),
        scheduled_time=payload_dict.get("scheduled_time", _UNSET),
        scheduled_end_time=payload_dict.get("scheduled_end_time", _UNSET),
    )

    if schedule_changed:
        if task.schedule_type:
            service.sync_task_to_scheduled_items(task, current_user.id)
        else:
            # schedule_type 被清除，删除所有关联排期
            si_service = ScheduledItemService(db)
            for item in si_service.list_by_task_id(current_user.id, task.id):
                si_service.soft_delete(item)
    elif title_changed:
        si_service = ScheduledItemService(db)
        for item in si_service.list_by_task_id(current_user.id, task.id):
            si_service.update(item, title=task.title)

    db.commit()
    return ApiResponse(data=_to_item(task), message="任务已更新")


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict[str, str]]:
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    service.delete_task(task)
    db.commit()
    return ApiResponse(data={"id": task.id}, message="任务已删除")


@router.patch("/{task_id}/complete")
def complete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskItemDTO]:
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    service.complete_task(task)
    db.commit()
    return ApiResponse(data=_to_item(task), message="任务已完成")


@router.get("/{task_id}/scheduled-items")
def list_task_scheduled_items(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemListResponse]:
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    items = service.list_scheduled_items_for_task(current_user.id, task_id)
    return ApiResponse(data=ScheduledItemListResponse(
        items=[_si_to_dto(item) for item in items]
    ))


@router.post("/{task_id}/scheduled-items/regenerate")
def regenerate_task_scheduled_items(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ScheduledItemListResponse]:
    service = TaskService(db)
    task = service.get_task(current_user.id, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not task.schedule_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务未配置日期范围，无法重新生成排期"
        )
    items = service.sync_task_to_scheduled_items(task, current_user.id)
    db.commit()
    return ApiResponse(
        data=ScheduledItemListResponse(items=[_si_to_dto(item) for item in items]),
        message=f"已重新生成 {len(items)} 个排期"
    )
