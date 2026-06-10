from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, time as dt_time
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from app.db.session import SessionLocal
from app.models import TaskItem, User, UserSettings
from app.models.enums import ReminderTargetType, ScheduledItemStatus
from app.services.conflict_service import ConflictService
from app.services.reminder_service import ReminderService
from app.services.scheduled_item_service import ScheduledItemService
from app.services.task_service import TaskService

_user_id: str = ""
_user_settings: UserSettings | None = None


def set_user_id(user_id: str, db=None) -> None:
    global _user_id, _user_settings
    _user_id = user_id
    if db:
        user = db.query(User).filter(User.id == user_id).first()
        _user_settings = user.settings if user else None
    else:
        _user_settings = None


def _get_user_id() -> str:
    return _user_id


def _get_default_remind_minutes() -> int:
    if _user_settings and _user_settings.default_remind_before_minutes:
        return _user_settings.default_remind_before_minutes
    return 0


def _item_to_dict(item: object) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "start_time": item.start_time.isoformat() if item.start_time else None,
        "end_time": item.end_time.isoformat() if item.end_time else None,
        "timezone": item.timezone,
        "location": item.location,
        "status": item.status,
        "remind_before_minutes": item.remind_before_minutes,
    }


def _task_to_dict(task: TaskItem) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "estimated_minutes": task.estimated_minutes,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "priority": task.priority,
        "status": task.status,
    }


@tool
def create_scheduled_item(
    title: str,
    start_time: str,
    end_time: str | None = None,
    location: str | None = None,
    remind_before_minutes: int = 0,
    timezone: str = "Asia/Shanghai",
) -> dict:
    """创建日程安排。

    Args:
        title: 日程标题
        start_time: 开始时间，ISO 8601 格式（如 2026-06-10T15:00:00+08:00）
        end_time: 结束时间，可选，默认开始后1小时
        location: 地点，可选
        remind_before_minutes: 提前提醒分钟数，默认0表示使用用户设置的默认值
        timezone: 时区，默认 Asia/Shanghai
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ScheduledItemService(db)
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time) if end_time else start + timedelta(hours=1)

        # 当 remind_before_minutes 为 0 时，使用用户的默认设置
        actual_remind_minutes = remind_before_minutes if remind_before_minutes > 0 else _get_default_remind_minutes()

        item = service.create(
            user_id=user_id,
            title=title,
            start_time=start,
            end_time=end,
            timezone=timezone,
            location=location,
            remind_before_minutes=actual_remind_minutes,
            source="agent",
        )
        trigger_time = start - timedelta(minutes=remind_before_minutes)
        ReminderService(db).create_for_target(
            user_id=user_id,
            target_type=ReminderTargetType.SCHEDULED_ITEM.value,
            target_id=item.id,
            title=item.title,
            trigger_time=trigger_time,
        )
        conflicts = ConflictService(db).detect_item_conflicts(user_id, item)
        db.commit()
        conflict_info = []
        if conflicts:
            conflict_info = [
                {"id": c.id, "title": c.title, "status": c.status}
                for c in conflicts
            ]
        msg = "安排已创建"
        if conflict_info:
            msg += f"，检测到 {len(conflict_info)} 个冲突"
        return {"success": True, "data": _item_to_dict(item), "conflicts": conflict_info, "message": msg}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def query_scheduled_items(
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
    on_date: str | None = None,
) -> dict:
    """查询日程安排。按日期范围或关键词查询。

    Args:
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        keyword: 搜索关键词
        on_date: 指定日期，格式 YYYY-MM-DD（查询某一天的安排）
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ScheduledItemService(db)

        if keyword:
            on = date.fromisoformat(on_date) if on_date else None
            items = service.search(user_id, keyword, on)
        elif start_date and end_date:
            start = datetime.combine(date.fromisoformat(start_date), datetime.min.time())
            end = datetime.combine(date.fromisoformat(end_date), datetime.max.time())
            items = service.list_by_date_range(user_id, start_time=start, end_time=end)
        elif on_date:
            items = service.list_by_date(user_id, date.fromisoformat(on_date))
        else:
            items = []

        return {
            "success": True,
            "data": [_item_to_dict(item) for item in items],
            "message": f"安排查询完成，共 {len(items)} 条",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def update_scheduled_item(
    item_id: str,
    title: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    location: str | None = None,
    remind_before_minutes: int | None = None,
) -> dict:
    """修改日程安排。

    Args:
        item_id: 日程ID
        title: 新标题
        start_time: 新开始时间，ISO 8601 格式
        end_time: 新结束时间，ISO 8601 格式
        location: 新地点
        remind_before_minutes: 新提前提醒分钟数
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ScheduledItemService(db)
        item = service.get(user_id, item_id)
        if item is None:
            return {"success": False, "error": "安排不存在"}

        start = datetime.fromisoformat(start_time) if start_time else None
        end = datetime.fromisoformat(end_time) if end_time else None

        item = service.update(
            item,
            title=title,
            start_time=start,
            end_time=end,
            location=location,
            remind_before_minutes=remind_before_minutes,
        )
        if start is not None or remind_before_minutes is not None:
            effective_start = start or item.start_time
            effective_remind_before = remind_before_minutes if remind_before_minutes is not None else (item.remind_before_minutes or 0)
            ReminderService(db).cancel_by_target(user_id=user_id, target_id=item.id)
            ReminderService(db).create_for_target(
                user_id=user_id,
                target_type=ReminderTargetType.SCHEDULED_ITEM.value,
                target_id=item.id,
                title=item.title,
                trigger_time=effective_start - timedelta(minutes=effective_remind_before),
            )
        db.commit()
        return {"success": True, "data": _item_to_dict(item), "message": "安排已更新"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def delete_scheduled_item(item_id: str) -> dict:
    """删除日程安排。

    Args:
        item_id: 日程ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ScheduledItemService(db)
        item = service.get(user_id, item_id)
        if item is None:
            return {"success": False, "error": "安排不存在"}
        service.soft_delete(item)
        db.commit()
        return {"success": True, "data": {"id": item.id}, "message": "安排已删除"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def create_task(
    title: str,
    estimated_minutes: int | None = None,
    description: str | None = None,
    deadline: str | None = None,
    priority: str = "medium",
) -> dict:
    """创建任务。

    Args:
        title: 任务标题
        estimated_minutes: 预估耗时（分钟）
        description: 任务描述
        deadline: 截止时间，ISO 8601 格式
        priority: 优先级，low/medium/high
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        dl = datetime.fromisoformat(deadline) if deadline else None
        task = TaskService(db).create_task(
            user_id=user_id,
            title=title,
            description=description,
            estimated_minutes=estimated_minutes,
            deadline=dl,
            priority=priority,
        )
        db.commit()
        return {"success": True, "data": _task_to_dict(task), "message": "任务已创建"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def query_tasks(status: str | None = None) -> dict:
    """查询任务列表。

    Args:
        status: 筛选状态，pending/completed，不填返回全部
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        tasks = TaskService(db).list_tasks(user_id, status)[0]
        return {
            "success": True,
            "data": [_task_to_dict(t) for t in tasks],
            "message": f"任务查询完成，共 {len(tasks)} 条",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def complete_task(task_id: str) -> dict:
    """完成任务。

    Args:
        task_id: 任务ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = TaskService(db)
        task = service.get_task(user_id, task_id)
        if task is None:
            return {"success": False, "error": "任务不存在"}
        service.complete_task(task)
        db.commit()
        return {"success": True, "data": _task_to_dict(task), "message": "任务已完成"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def delete_task(task_id: str) -> dict:
    """删除任务。

    Args:
        task_id: 任务ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = TaskService(db)
        task = service.get_task(user_id, task_id)
        if task is None:
            return {"success": False, "error": "任务不存在"}
        service.delete_task(task)
        db.commit()
        return {"success": True, "data": {"id": task.id}, "message": "任务已删除"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def analyze_day(plan_date: str) -> dict:
    """分析某天的安排和任务。

    Args:
        plan_date: 日期，格式 YYYY-MM-DD
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        d = date.fromisoformat(plan_date)
        item_service = ScheduledItemService(db)
        task_service = TaskService(db)
        items = item_service.list_by_date(user_id, d)
        tasks = task_service.list_tasks(user_id)[0]
        return {
            "success": True,
            "data": {
                "items": [_item_to_dict(i) for i in items],
                "tasks": [_task_to_dict(t) for t in tasks],
            },
            "message": "安排分析完成",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def find_free_slots(
    plan_date: str,
    timezone: str = "Asia/Shanghai",
    workday_start: str = "09:00",
    workday_end: str = "22:00",
) -> dict:
    """查找某天的空闲时间段。

    Args:
        plan_date: 日期，格式 YYYY-MM-DD
        timezone: 时区
        workday_start: 工作时间开始，格式 HH:MM
        workday_end: 工作时间结束，格式 HH:MM
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        from datetime import UTC, datetime as dt

        d = date.fromisoformat(plan_date)
        service = ScheduledItemService(db)
        items = service.list_by_date(user_id, d)

        user_tz = ZoneInfo(timezone)
        start_parts = workday_start.split(":")
        end_parts = workday_end.split(":")
        day_start_local = dt(d.year, d.month, d.day, int(start_parts[0]), int(start_parts[1]), tzinfo=user_tz)
        day_end_local = dt(d.year, d.month, d.day, int(end_parts[0]), int(end_parts[1]), tzinfo=user_tz)
        day_start = day_start_local.astimezone(UTC)
        day_end = day_end_local.astimezone(UTC)

        active_items = sorted(
            [i for i in items if i.status == "active" and i.end_time.astimezone(UTC) > day_start and i.start_time.astimezone(UTC) < day_end],
            key=lambda x: x.start_time,
        )

        free_slots = []
        cursor = day_start
        for item in active_items:
            item_start = max(item.start_time.astimezone(UTC), day_start)
            item_end = min(item.end_time.astimezone(UTC), day_end)
            if item_start > cursor:
                slot_minutes = int((item_start - cursor).total_seconds() // 60)
                free_slots.append({
                    "start_time": cursor.isoformat(),
                    "end_time": item_start.isoformat(),
                    "duration_minutes": slot_minutes,
                })
            if item_end > cursor:
                cursor = item_end
        if cursor < day_end:
            slot_minutes = int((day_end - cursor).total_seconds() // 60)
            free_slots.append({
                "start_time": cursor.isoformat(),
                "end_time": day_end.isoformat(),
                "duration_minutes": slot_minutes,
            })
        return {"success": True, "data": free_slots, "message": "空闲时间已计算"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def plan_tasks_into_day(plan_date: str) -> dict:
    """将未排期任务排入某天生成安排草案。

    Args:
        plan_date: 日期，格式 YYYY-MM-DD
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        d = date.fromisoformat(plan_date)
        service = ScheduledItemService(db)
        items = service.generate_day_drafts(user_id, d)
        db.commit()
        return {
            "success": True,
            "data": [_item_to_dict(i) for i in items],
            "message": f"已生成 {len(items)} 个安排草案",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def confirm_plan(plan_date: str) -> dict:
    """确认安排草案，将草案状态改为 active。

    Args:
        plan_date: 日期，格式 YYYY-MM-DD
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        d = date.fromisoformat(plan_date)
        count = ScheduledItemService(db).confirm_drafts_for_date(user_id, d)
        db.commit()
        return {"success": True, "data": {"confirmed_count": count}, "message": f"已确认 {count} 个安排"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def detect_conflicts(plan_date: str | None = None) -> dict:
    """检测日程冲突。

    Args:
        plan_date: 日期，格式 YYYY-MM-DD，不填则检测全部
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ConflictService(db)
        if plan_date:
            conflicts = service.detect_day_conflicts(user_id)
        else:
            conflicts = service.list_conflicts(user_id)[0]
        db.commit()
        return {
            "success": True,
            "data": [{"id": c.id, "title": c.title, "status": c.status} for c in conflicts],
            "message": f"冲突检测完成，共 {len(conflicts)} 个",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def suggest_reschedule(conflict_id: str) -> dict:
    """根据冲突建议调整时间。

    Args:
        conflict_id: 冲突ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        conflict_service = ConflictService(db)
        conflict = conflict_service.get_conflict(user_id, conflict_id)
        if conflict is None:
            return {"success": False, "error": "冲突不存在"}
        if conflict.status != "open":
            return {"success": False, "error": "冲突已处理"}

        related = conflict.related_item_ids or {}
        item_id_a = related.get("current")
        item_id_b = related.get("other")
        if not item_id_a or not item_id_b:
            return {"success": False, "error": "冲突缺少关联安排"}

        item_service = ScheduledItemService(db)
        item_a = item_service.get(user_id, item_id_a)
        item_b = item_service.get(user_id, item_id_b)
        if item_a is None or item_b is None:
            return {"success": False, "error": "关联安排不存在"}

        conflict_date = item_a.start_time.astimezone(UTC).date()
        free_slots_result = find_free_slots.invoke(
            {"plan_date": conflict_date.isoformat()}
        )
        free_slots = free_slots_result.get("data", [])

        suggestions = []
        for item in [item_a, item_b]:
            duration = int((item.end_time - item.start_time).total_seconds() // 60)
            for slot in free_slots:
                if slot["duration_minutes"] >= duration:
                    slot_start = datetime.fromisoformat(slot["start_time"])
                    slot_end = slot_start + timedelta(minutes=duration)
                    suggestions.append({
                        "item_id": item.id,
                        "item_title": item.title,
                        "suggested_start": slot_start.isoformat(),
                        "suggested_end": slot_end.isoformat(),
                    })
                    break
        return {
            "success": True,
            "data": {"conflict_id": conflict.id, "suggestions": suggestions},
            "message": "已生成调整建议",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def create_reminder(
    title: str,
    trigger_time: str,
    target_type: str = "scheduled_item",
    target_id: str = "",
) -> dict:
    """创建提醒。

    Args:
        title: 提醒标题
        trigger_time: 触发时间，ISO 8601 格式
        target_type: 关联类型
        target_id: 关联ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        job = ReminderService(db).create_for_target(
            user_id=user_id,
            target_type=target_type,
            target_id=target_id,
            title=title,
            trigger_time=datetime.fromisoformat(trigger_time),
        )
        db.commit()
        return {"success": True, "data": {"id": job.id}, "message": "提醒已创建"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def query_reminders(status: str = "pending") -> dict:
    """查询提醒列表。

    Args:
        status: 筛选状态，pending/fired/canceled
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        items, total = ReminderService(db).list_jobs(user_id, status=status)
        return {
            "success": True,
            "data": [
                {
                    "id": item.id,
                    "title": item.title,
                    "trigger_time": item.trigger_time.isoformat(),
                    "status": item.status,
                }
                for item in items
            ],
            "message": f"提醒查询完成，共 {total} 条",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def cancel_reminder(reminder_id: str) -> dict:
    """取消提醒。

    Args:
        reminder_id: 提醒ID
    """
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        service = ReminderService(db)
        job = service.get_job(user_id, reminder_id)
        if job is None:
            return {"success": False, "error": "提醒不存在"}
        service.cancel_job(job)
        db.commit()
        return {"success": True, "data": {"id": job.id}, "message": "提醒已取消"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@tool
def ask_user_clarification(prompt: str) -> dict:
    """当信息不足时向用户追问。

    Args:
        prompt: 追问内容
    """
    return {"success": True, "data": {"prompt": prompt}, "message": prompt}


ALL_TOOLS = [
    create_scheduled_item,
    query_scheduled_items,
    update_scheduled_item,
    delete_scheduled_item,
    create_task,
    query_tasks,
    complete_task,
    delete_task,
    analyze_day,
    find_free_slots,
    plan_tasks_into_day,
    confirm_plan,
    detect_conflicts,
    suggest_reschedule,
    create_reminder,
    query_reminders,
    cancel_reminder,
    ask_user_clarification,
]
