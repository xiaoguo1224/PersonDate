from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import TaskItem, User
from app.schemas.common import ApiResponse
from app.schemas.task import TaskCreateRequest, TaskItemDTO, TaskListResponse, TaskUpdateRequest
from app.services.task_service import TaskService

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
    )


@router.get("")
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskListResponse]:
    items = [_to_item(task) for task in TaskService(db).list_tasks(current_user.id)]
    return ApiResponse(data=TaskListResponse(items=items))


@router.post("")
def create_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskItemDTO]:
    task = TaskService(db).create_task(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        estimated_minutes=payload.estimated_minutes,
        deadline=payload.deadline,
        priority=payload.priority,
    )
    db.commit()
    return ApiResponse(data=_to_item(task), message="任务已创建")


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
    task = service.update_task(
        task,
        title=payload.title,
        description=payload.description,
        estimated_minutes=payload.estimated_minutes,
        deadline=payload.deadline,
        priority=payload.priority,
    )
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
