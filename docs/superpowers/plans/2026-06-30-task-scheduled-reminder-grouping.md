# 任务排期提醒补齐与提醒页折叠展示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让任务生成或确认出的排期自动维护每天一条真实提醒，并让提醒页按用户时区将同任务同提醒时刻的多天提醒折叠展示。

**Architecture:** 后端把“排期 -> 唯一 pending 提醒”的同步规则统一收口到 `ReminderService`，再由任务排期同步、草稿确认、排期更新/删除等入口复用。前端不改变提醒数据结构，只把提醒列表先转换成“单条节点 / 折叠组节点”，分组计算全部基于用户时区的本地日期和本地时钟值。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest, Next.js 15, React 19, TypeScript, Ant Design, dayjs

---

## File Structure

### Backend files to modify

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/reminder.py` | 给提醒响应增加 `source_task_id` |
| `backend/app/api/routes/reminders.py` | 将关联 `ScheduledItem.source_task_id` 透传到提醒响应 |
| `backend/app/services/reminder_service.py` | 新增统一的排期提醒同步入口，负责取消旧 pending 和重建新 pending |
| `backend/app/services/task_service.py` | 任务生成/重生成排期时写入默认提醒分钟数并同步提醒 |
| `backend/app/services/scheduled_item_service.py` | 草稿确认返回已确认排期，供调用侧补建提醒 |
| `backend/app/api/routes/tasks.py` | 保持任务入口调用任务服务，必要时补充用户时区传递 |
| `backend/app/api/routes/scheduled_items.py` | 更新、删除排期时统一走提醒同步规则 |
| `backend/app/agent/tools.py` | `confirm_plan`、`update_scheduled_item`、`delete_scheduled_item` 统一复用提醒同步逻辑 |

### Frontend files to modify

| File | Responsibility |
| --- | --- |
| `web/lib/dashboard.ts` | 扩展 `ReminderItem` 类型 |
| `web/app/dashboard/reminders/page.tsx` | 提醒页按用户时区分组并渲染折叠组 |

### Tests / verification files

| File | Responsibility |
| --- | --- |
| `backend/tests/test_reminder_service.py` | 覆盖唯一 pending 提醒同步规则 |
| `backend/tests/test_tasks_route.py` | 覆盖任务自动排期后提醒生成与更新 |
| `backend/tests/test_agent_debug_flow.py` | 覆盖草稿确认后提醒生成 |

### Timezone invariants

- 后端凡是按“某一天”筛草稿、排期、提醒，都必须继续使用用户时区，而不是裸 `UTC date()`。
- 前端分组不能直接用 ISO 字符串截断，必须通过 `useDashboardTimezone()` 取到用户时区，再用 `getDateKey()` / `formatClock()` 计算本地日期与本地时钟值。
- 任何“08:00 / 10:00 是否同组”的判断，都以用户当前时区看到的 `HH:mm` 为准。

---

### Task 1: 先写提醒同步服务的失败测试，再补服务入口

**Files:**
- Modify: `backend/tests/test_reminder_service.py`
- Modify: `backend/app/services/reminder_service.py`

- [ ] **Step 1: 写提醒同步服务的失败测试**

在 `backend/tests/test_reminder_service.py` 末尾追加下面 3 个测试，先只写测试不实现：

```python
from app.models import ReminderJob, ReminderStatus, ScheduledItem
from app.models.enums import ScheduledItemStatus


def test_sync_pending_for_scheduled_item_replaces_existing_pending_job() -> None:
    session = _build_session()
    service = ReminderService(session)

    item = ScheduledItem(
        id="item-1",
        user_id="user-1",
        title="游泳",
        start_time=datetime(2026, 7, 2, 0, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 2, 1, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
        source="task",
        source_task_id="task-1",
        remind_before_minutes=60,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.flush()

    old_job = service.create_for_target(
        user_id="user-1",
        target_type="scheduled_item",
        target_id="item-1",
        title="游泳",
        trigger_time=datetime(2026, 7, 1, 22, 0, tzinfo=UTC),
    )
    session.commit()

    item.start_time = datetime(2026, 7, 2, 2, 0, tzinfo=UTC)
    new_job = service.sync_pending_for_scheduled_item(user_id="user-1", item=item)
    session.commit()

    jobs = list(
        session.query(ReminderJob)
        .filter(ReminderJob.user_id == "user-1", ReminderJob.target_id == "item-1")
        .order_by(ReminderJob.created_at.asc())
    )

    assert new_job is not None
    assert len(jobs) == 2
    assert jobs[0].status == ReminderStatus.CANCELED.value
    assert jobs[1].status == ReminderStatus.PENDING.value
    assert jobs[1].trigger_time == datetime(2026, 7, 2, 1, 0, tzinfo=UTC)
    assert old_job.id != new_job.id


def test_sync_pending_for_scheduled_item_cancels_when_item_is_not_active() -> None:
    session = _build_session()
    service = ReminderService(session)

    item = ScheduledItem(
        id="item-2",
        user_id="user-1",
        title="写论文",
        start_time=datetime(2026, 7, 2, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        timezone="Asia/Shanghai",
        source="plan",
        source_task_id="task-2",
        remind_before_minutes=30,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.flush()
    service.create_for_target(
        user_id="user-1",
        target_type="scheduled_item",
        target_id="item-2",
        title="写论文",
        trigger_time=datetime(2026, 7, 2, 7, 30, tzinfo=UTC),
    )
    session.commit()

    item.status = ScheduledItemStatus.COMPLETED.value
    result = service.sync_pending_for_scheduled_item(user_id="user-1", item=item)
    session.commit()

    jobs = list(session.query(ReminderJob).filter(ReminderJob.target_id == "item-2"))
    assert result is None
    assert len(jobs) == 1
    assert jobs[0].status == ReminderStatus.CANCELED.value


def test_sync_pending_for_scheduled_item_skips_expired_trigger_time() -> None:
    session = _build_session()
    service = ReminderService(session)

    item = ScheduledItem(
        id="item-3",
        user_id="user-1",
        title="补发失败示例",
        start_time=datetime.now(UTC) - timedelta(minutes=10),
        end_time=datetime.now(UTC) + timedelta(minutes=20),
        timezone="Asia/Shanghai",
        source="task",
        source_task_id="task-3",
        remind_before_minutes=30,
        status=ScheduledItemStatus.ACTIVE.value,
    )
    session.add(item)
    session.commit()

    result = service.sync_pending_for_scheduled_item(user_id="user-1", item=item)
    session.commit()

    jobs = list(session.query(ReminderJob).filter(ReminderJob.target_id == "item-3"))
    assert result is None
    assert jobs == []
```

- [ ] **Step 2: 运行单测确认它们按预期失败**

Run:

```bash
cd backend
uv run pytest tests/test_reminder_service.py -k "sync_pending_for_scheduled_item" -v
```

Expected: 失败并提示 `ReminderService` 没有 `sync_pending_for_scheduled_item`，或断言不满足。

- [ ] **Step 3: 用最小实现补 `ReminderService.sync_pending_for_scheduled_item(...)`**

在 `backend/app/services/reminder_service.py` 里增加这个方法，并只做本任务需要的逻辑：

```python
from app.models import ReminderJob, ReminderStatus
from app.models.enums import ReminderTargetType, ScheduledItemStatus


def sync_pending_for_scheduled_item(
    self,
    *,
    user_id: str,
    item,
    now: datetime | None = None,
) -> ReminderJob | None:
    now = now or datetime.now(UTC)
    self.cancel_by_target(user_id=user_id, target_id=item.id)

    if item.status != ScheduledItemStatus.ACTIVE.value:
        return None

    remind_before = item.remind_before_minutes
    if remind_before is None:
        return None

    trigger_time = item.start_time - timedelta(minutes=remind_before)
    if trigger_time <= now:
        return None

    return self.create_for_target(
        user_id=user_id,
        target_type=ReminderTargetType.SCHEDULED_ITEM.value,
        target_id=item.id,
        title=item.title,
        trigger_time=trigger_time,
    )
```

- [ ] **Step 4: 重跑单测直到通过**

Run:

```bash
cd backend
uv run pytest tests/test_reminder_service.py -k "sync_pending_for_scheduled_item" -v
```

Expected: 3 个新测试 PASS，原有 `list_jobs` 测试继续 PASS。

- [ ] **Step 5: 提交这一小步**

```bash
git add backend/tests/test_reminder_service.py backend/app/services/reminder_service.py
git commit -m "test(reminder): 补齐排期提醒同步服务"
```

---

### Task 2: 先写任务排期提醒的失败测试，再补任务服务与提醒响应字段

**Files:**
- Modify: `backend/tests/test_tasks_route.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/schemas/reminder.py`
- Modify: `backend/app/api/routes/reminders.py`

- [ ] **Step 1: 写任务自动排期与提醒响应字段的失败测试**

在 `backend/tests/test_tasks_route.py` 追加下面 2 个测试：

```python
from datetime import date

from sqlalchemy import select

from app.models import ReminderJob, ScheduledItem, UserSettings


def test_create_task_generates_daily_scheduled_items_with_reminders(
    client, admin_token, owner, db_session
) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 15
    db_session.commit()

    response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "游泳",
            "estimated_minutes": 60,
            "priority": "medium",
            "schedule_type": "duration_days",
            "start_date": "2026-07-01",
            "duration_days": 3,
            "time_type": "fixed",
            "scheduled_time": "08:00:00",
            "scheduled_end_time": "09:00:00",
        },
    )
    assert response.status_code == 200

    items = list(
        db_session.scalars(
            select(ScheduledItem)
            .where(ScheduledItem.user_id == owner.id, ScheduledItem.source_task_id.is_not(None))
            .order_by(ScheduledItem.start_time.asc())
        )
    )
    reminders = list(
        db_session.scalars(
            select(ReminderJob)
            .where(ReminderJob.user_id == owner.id)
            .order_by(ReminderJob.trigger_time.asc())
        )
    )

    assert len(items) == 3
    assert len(reminders) == 3
    assert all(item.remind_before_minutes == 15 for item in items)
    assert reminders[0].trigger_time.isoformat().startswith("2026-07-01T23:45:00")


def test_list_reminders_returns_source_task_id(client, admin_token, owner, db_session) -> None:
    headers = {"Authorization": f"Bearer {admin_token}"}
    settings = db_session.scalar(select(UserSettings).where(UserSettings.user_id == owner.id))
    settings.default_timezone = "Asia/Shanghai"
    settings.default_remind_before_minutes = 10
    db_session.commit()

    create_response = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "写论文",
            "estimated_minutes": 120,
            "priority": "high",
            "schedule_type": "duration_days",
            "start_date": "2026-07-02",
            "duration_days": 1,
            "time_type": "fixed",
            "scheduled_time": "10:00:00",
            "scheduled_end_time": "12:00:00",
        },
    )
    assert create_response.status_code == 200

    response = client.get("/api/reminders?status=pending", headers=headers)
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["source_task_id"]
    assert item["title"] == "写论文"
    assert item["remind_before_minutes"] == 10
```

- [ ] **Step 2: 运行这些测试，确认它们先失败**

Run:

```bash
cd backend
uv run pytest tests/test_tasks_route.py -k "generates_daily_scheduled_items_with_reminders or returns_source_task_id" -v
```

Expected: 失败，通常会是“提醒数量为 0”或提醒响应里缺少 `source_task_id`。

- [ ] **Step 3: 最小实现任务排期提醒和提醒响应字段**

先在 `backend/app/schemas/reminder.py` 里扩展响应：

```python
class ReminderDTO(BaseModel):
    id: str
    target_type: str
    target_id: str
    title: str
    conversation_id: str | None = None
    original_time: datetime | None = None
    trigger_time: datetime
    remind_before_minutes: int = 0
    source_task_id: str | None = None
    status: str
    retry_count: int
    max_retries: int
    error_message: str | None = None
    fired_at: datetime | None = None
```

再在 `backend/app/api/routes/reminders.py` 中透传：

```python
def _to_item(job: ReminderJob, scheduled_item: ScheduledItem | None = None) -> ReminderDTO:
    original_time = None
    remind_before = 0
    source_task_id = None
    if scheduled_item is not None:
        original_time = scheduled_item.start_time
        remind_before = scheduled_item.remind_before_minutes or 0
        source_task_id = scheduled_item.source_task_id
    return ReminderDTO(
        id=job.id,
        target_type=job.target_type,
        target_id=job.target_id,
        title=job.title,
        conversation_id=job.conversation_id,
        original_time=original_time,
        trigger_time=job.trigger_time,
        remind_before_minutes=remind_before,
        source_task_id=source_task_id,
        status=job.status,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        error_message=job.error_message,
        fired_at=job.fired_at,
    )
```

最后在 `backend/app/services/task_service.py` 中，把任务生成排期改成“写默认提醒分钟数 + 同步提醒”：

```python
from app.models import UserSettings
from app.services.reminder_service import ReminderService


def _default_remind_before_minutes(self, user_id: str) -> int:
    settings = self.db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings and settings.default_remind_before_minutes is not None:
        return settings.default_remind_before_minutes
    return 0


def sync_task_to_scheduled_items(
    self,
    task: TaskItem,
    user_id: str,
    timezone: str = "Asia/Shanghai",
) -> list[ScheduledItem]:
    from app.services.scheduled_item_service import ScheduledItemService

    si_service = ScheduledItemService(self.db)
    reminder_service = ReminderService(self.db)
    remind_before = self._default_remind_before_minutes(user_id)

    existing = si_service.list_by_task_id(user_id, task.id)
    for item in existing:
        if item.source != ScheduledItemSource.MANUAL.value:
            reminder_service.cancel_by_target(user_id=user_id, target_id=item.id)
            si_service.soft_delete(item)

    dates = self.get_dates_for_task(task, timezone=timezone)
    if not dates:
        return []

    mins = task.estimated_minutes or 60
    created: list[ScheduledItem] = []

    for d in dates:
        if task.time_type == TaskTimeType.FIXED and task.scheduled_time is not None:
            start_dt = _combine_local(d, task.scheduled_time, timezone)
            end_dt = (
                _combine_local(d, task.scheduled_end_time, timezone)
                if task.scheduled_end_time
                else start_dt + timedelta(minutes=mins)
            )
        else:
            slot = self._find_next_free_slot(user_id, d, mins, timezone)
            if slot is None:
                continue
            start_dt, end_dt = slot

        item = si_service.create(
            user_id=user_id,
            title=task.title,
            start_time=start_dt,
            end_time=end_dt,
            timezone=timezone,
            source=ScheduledItemSource.TASK.value,
            source_task_id=task.id,
            remind_before_minutes=remind_before,
            status=ScheduledItemStatus.ACTIVE.value,
        )
        reminder_service.sync_pending_for_scheduled_item(user_id=user_id, item=item)
        created.append(item)

    return created
```

- [ ] **Step 4: 重跑测试直到通过**

Run:

```bash
cd backend
uv run pytest tests/test_tasks_route.py -k "generates_daily_scheduled_items_with_reminders or returns_source_task_id" -v
```

Expected: 两个新增测试 PASS；注意第一个测试的 UTC 时间断言成立，说明 `Asia/Shanghai 08:00 - 15 分钟` 正确转换成前一日 `23:45 UTC`。

- [ ] **Step 5: 提交这一小步**

```bash
git add backend/tests/test_tasks_route.py backend/app/services/task_service.py backend/app/schemas/reminder.py backend/app/api/routes/reminders.py
git commit -m "feat(tasks): 补齐任务排期提醒与任务来源字段"
```

---

### Task 3: 先写草稿确认与排期更新的失败测试，再统一确认/更新链路

**Files:**
- Modify: `backend/tests/test_agent_debug_flow.py`
- Modify: `backend/app/services/scheduled_item_service.py`
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/api/routes/scheduled_items.py`

- [ ] **Step 1: 写草稿确认后创建提醒、更新排期后同步提醒的失败测试**

在 `backend/tests/test_agent_debug_flow.py` 里补 2 个断言块，先让它们失败：

```python
def test_plan_task_and_confirm(db_session, graph) -> None:
    owner = _create_owner(db_session)

    graph.invoke(
        current_user=owner,
        message="明天写论文 2 小时，帮我安排一下",
        conversation_id="debug",
    )
    db_session.commit()

    draft_items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
                ScheduledItem.status == "draft",
            )
        )
    )
    draft_reminders = list(
        db_session.scalars(
            select(ReminderJob).where(ReminderJob.user_id == owner.id)
        )
    )

    assert len(draft_items) >= 1
    assert draft_reminders == []

    confirm_state = graph.invoke(current_user=owner, message="确认", conversation_id="debug")
    db_session.commit()

    confirmed_items = list(
        db_session.scalars(
            select(ScheduledItem).where(
                ScheduledItem.user_id == owner.id,
                ScheduledItem.status == "active",
            )
        )
    )
    pending_reminders = list(
        db_session.scalars(
            select(ReminderJob).where(
                ReminderJob.user_id == owner.id,
                ReminderJob.status == "pending",
            )
        )
    )

    assert "计划已确认" in (confirm_state.final_response or "")
    assert len(confirmed_items) >= 1
    assert len(pending_reminders) == len(confirmed_items)


def test_update_and_delete_event(db_session, graph) -> None:
    owner = _create_owner(db_session)
    graph.invoke(current_user=owner, message="明天下午 3 点开会", conversation_id="debug")
    db_session.commit()

    original_reminder = db_session.scalar(
        select(ReminderJob).where(ReminderJob.user_id == owner.id)
    )
    assert original_reminder is not None

    graph.invoke(
        current_user=owner,
        message="把明天下午 3 点的会议改到 4 点",
        conversation_id="debug",
    )
    db_session.commit()

    reminders = list(
        db_session.scalars(
            select(ReminderJob)
            .where(ReminderJob.user_id == owner.id)
            .order_by(ReminderJob.created_at.asc())
        )
    )

    assert len(reminders) == 2
    assert reminders[0].status == "canceled"
    assert reminders[1].status == "pending"
    assert reminders[1].trigger_time.hour == 16
```

- [ ] **Step 2: 跑这组测试，确认它们先失败**

Run:

```bash
cd backend
uv run pytest tests/test_agent_debug_flow.py -k "plan_task_and_confirm or update_and_delete_event" -v
```

Expected: 失败，通常会是确认后没有 reminder，或更新后没有取消旧 reminder / 新 reminder 时间不对。

- [ ] **Step 3: 最小实现草稿确认和排期更新链路**

先把 `backend/app/services/scheduled_item_service.py` 的确认接口改成返回排期对象：

```python
def confirm_drafts_for_date(self, user_id: str, plan_date: date) -> list[ScheduledItem]:
    timezone_name = _get_user_timezone_name(self.db, user_id)
    _, _, start_utc, end_utc = _get_day_bounds(plan_date, timezone_name)
    stmt = select(ScheduledItem).where(
        ScheduledItem.user_id == user_id,
        ScheduledItem.start_time >= start_utc,
        ScheduledItem.start_time < end_utc,
        ScheduledItem.status == ScheduledItemStatus.DRAFT.value,
    )
    items = list(self.db.scalars(stmt))
    for item in items:
        item.status = ScheduledItemStatus.ACTIVE.value
    self.db.flush()
    invalidate_user_events(user_id)
    return items
```

再把 `backend/app/agent/tools.py` 的确认工具改成确认后补提醒：

```python
@tool
def confirm_plan(plan_date: str) -> dict:
    user_id = _get_user_id()
    db = SessionLocal()
    try:
        d = date.fromisoformat(plan_date)
        items = ScheduledItemService(db).confirm_drafts_for_date(user_id, d)
        reminder_service = ReminderService(db)
        for item in items:
            reminder_service.sync_pending_for_scheduled_item(user_id=user_id, item=item)
        db.commit()
        return {
            "success": True,
            "data": {"confirmed_count": len(items)},
            "message": f"已确认 {len(items)} 个安排",
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
```

最后把 `backend/app/api/routes/scheduled_items.py` 与 `backend/app/agent/tools.py` 的排期更新逻辑统一成服务调用：

```python
reminder_service = ReminderService(db)
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
reminder_service.sync_pending_for_scheduled_item(user_id=current_user.id, item=item)
```

删除时也统一先取消提醒再删排期：

```python
reminder_service = ReminderService(db)
reminder_service.cancel_by_target(user_id=current_user.id, target_id=item.id)
service.soft_delete(item)
```

- [ ] **Step 4: 重跑测试直到通过**

Run:

```bash
cd backend
uv run pytest tests/test_agent_debug_flow.py -k "plan_task_and_confirm or update_and_delete_event" -v
```

Expected: 草稿阶段 reminder 为 0，确认后 reminder 数量和 active 排期数一致；更新排期后旧 reminder 变 `canceled`，新 reminder 为 `pending`。

- [ ] **Step 5: 提交这一小步**

```bash
git add backend/tests/test_agent_debug_flow.py backend/app/services/scheduled_item_service.py backend/app/agent/tools.py backend/app/api/routes/scheduled_items.py
git commit -m "fix(reminder): 统一草稿确认与排期更新提醒同步"
```

---

### Task 4: 抽出前端分组纯函数，按用户时区折叠渲染提醒页

**Files:**
- Modify: `web/lib/dashboard.ts`
- Modify: `web/app/dashboard/reminders/page.tsx`

- [ ] **Step 1: 先在提醒页里写出会失败的分组纯函数用例**

因为 `web` 当前没有测试 runner，不新增新栈；先把分组逻辑抽成局部纯函数，并在文件内用固定示例数据驱动实现。先写出目标形状：

```typescript
type ReminderDisplayNode =
  | { kind: "single"; reminder: ReminderItem }
  | {
      kind: "group";
      key: string;
      title: string;
      triggerClock: string;
      remindBeforeMinutes: number;
      status: string;
      reminders: ReminderItem[];
      dateKeys: string[];
    };

function buildReminderDisplayNodes(
  reminders: ReminderItem[],
  timezone: string,
): ReminderDisplayNode[] {
  // 先保留空实现，下一步补齐
  return reminders.map((reminder) => ({ kind: "single", reminder }));
}
```

并在同文件注释块里固定一组验收样例，作为实现对照：

```typescript
/*
验收样例：
- 同一 source_task_id，2026-07-01/02/03 的 trigger_time 在 Asia/Shanghai 下均为 08:00，应该产出一个 group 节点
- 其中一条改成 10:00，应该拆成一个 group + 一个 single
- 没有 source_task_id 的提醒必须保持 single
*/
```

- [ ] **Step 2: 先跑现有前端检查，确认代码未完成时会暴露类型或渲染问题**

Run:

```bash
cd web
pnpm typecheck
```

Expected: 如果你已经接入了新的 `ReminderDisplayNode` 但还没补渲染分支，可能会有类型错误；这一步就是先把失败暴露出来。

- [ ] **Step 3: 最小实现分组逻辑和渲染**

先在 `web/lib/dashboard.ts` 扩展提醒类型：

```typescript
export type ReminderItem = {
  id: string;
  target_type: string;
  target_id: string;
  title: string;
  original_time?: string | null;
  trigger_time: string;
  remind_before_minutes: number;
  source_task_id?: string | null;
  status: string;
  retry_count?: number;
  max_retries?: number;
  error_message?: string | null;
  fired_at?: string | null;
  conversation_id?: string | null;
};
```

再在 `web/app/dashboard/reminders/page.tsx` 中补分组函数，注意全部走 `timezone`：

```typescript
function buildReminderDisplayNodes(
  reminders: ReminderItem[],
  timezone: string,
): ReminderDisplayNode[] {
  const grouped = new Map<string, ReminderItem[]>();
  const singles: ReminderDisplayNode[] = [];

  for (const reminder of reminders) {
    if (
      reminder.target_type !== "scheduled_item" ||
      !reminder.source_task_id
    ) {
      singles.push({ kind: "single", reminder });
      continue;
    }

    const triggerClock = formatClock(reminder.trigger_time, timezone);
    const groupKey = [
      reminder.source_task_id,
      reminder.status,
      String(reminder.remind_before_minutes ?? 0),
      triggerClock,
    ].join("::");

    const bucket = grouped.get(groupKey) ?? [];
    bucket.push(reminder);
    grouped.set(groupKey, bucket);
  }

  const groupNodes: ReminderDisplayNode[] = Array.from(grouped.entries()).flatMap(
    ([key, bucket]) => {
      if (bucket.length === 1) {
        return [{ kind: "single", reminder: bucket[0] }];
      }

      const sorted = [...bucket].sort((a, b) => {
        return new Date(a.trigger_time).getTime() - new Date(b.trigger_time).getTime();
      });

      return [
        {
          kind: "group",
          key,
          title: sorted[0].title,
          triggerClock: formatClock(sorted[0].trigger_time, timezone),
          remindBeforeMinutes: sorted[0].remind_before_minutes ?? 0,
          status: sorted[0].status,
          reminders: sorted,
          dateKeys: sorted.map((item) => getDateKey(item.trigger_time, timezone)),
        },
      ];
    },
  );

  return [...groupNodes, ...singles].sort((a, b) => {
    const aTime = a.kind === "single" ? a.reminder.trigger_time : a.reminders[0].trigger_time;
    const bTime = b.kind === "single" ? b.reminder.trigger_time : b.reminders[0].trigger_time;
    return new Date(aTime).getTime() - new Date(bTime).getTime();
  });
}
```

然后把 `filteredReminders.map(...)` 改成 `displayNodes.map(...)`，组节点用 `Collapse` 或 `Card + 内层列表` 展开渲染，单条节点继续沿用现有按钮：

```tsx
const displayNodes = useMemo(
  () => buildReminderDisplayNodes(filteredReminders, timezone),
  [filteredReminders, timezone],
);
```

渲染组节点时，标题区至少显示：

```tsx
<Text strong>{node.title}</Text>
<Tag color={getStatusColor(node.status)}>{node.status}</Tag>
<Tag color="blue">{node.triggerClock}</Tag>
<Tag color="cyan">{node.reminders.length} 天</Tag>
<Text className="muted-text">
  日期：{node.dateKeys.map((value) => value.slice(5)).join(" / ")}
</Text>
```

组内展开后，再逐条渲染原来的“调整提醒时间 / 取消提醒 / 重新激活”按钮。

- [ ] **Step 4: 跑前端检查并做人工回归**

Run:

```bash
cd web
pnpm lint
pnpm typecheck
```

Expected: 两条命令都通过。

然后做人工回归：

1. 用同一任务造 3 条 `08:00` 提醒，确认提醒页显示 1 个折叠组
2. 把其中 1 条提醒改成 `10:00`，刷新后确认它从组里拆出来
3. 切换浏览器里用户时区设置数据，确认分组仍以页面展示时区为准

- [ ] **Step 5: 提交这一小步**

```bash
git add web/lib/dashboard.ts web/app/dashboard/reminders/page.tsx
git commit -m "feat(web): 折叠同任务同时间的多天提醒"
```

---

### Task 5: 全量验证并做最终整理

**Files:**
- No new files expected
- Re-touch only files already modified above if verification暴露缺陷

- [ ] **Step 1: 跑后端关键回归**

Run:

```bash
cd backend
uv run pytest tests/test_reminder_service.py tests/test_tasks_route.py tests/test_agent_debug_flow.py -v
```

Expected: 全部 PASS。

- [ ] **Step 2: 跑前端静态检查**

Run:

```bash
cd web
pnpm lint
pnpm typecheck
```

Expected: 全部 PASS。

- [ ] **Step 3: 做时区专项人工验证**

按下面顺序验证，不要跳：

```text
1. 用户 default_timezone = Asia/Shanghai
2. 创建 duration_days + fixed 08:00 的任务，确认数据库里 ScheduledItem.start_time 为 UTC 存储
3. 确认 ReminderJob.trigger_time = start_time - remind_before_minutes，且是 UTC
4. 提醒页显示时，08:00 组按上海时区折叠
5. 将其中一天提醒改成 10:00，刷新后单独拆组
6. 再验证草稿确认生成的提醒不会跨错本地日期
```

Expected:

```text
- 后端存 UTC
- 后端按用户时区算“哪一天”的草稿确认范围
- 前端按用户时区算分组日期和 HH:mm
```

- [ ] **Step 4: 提交最终修正**

```bash
git add backend/app backend/tests web/app web/lib
git commit -m "fix(reminder): 收敛任务排期提醒与折叠展示回归"
```

---

## Self-Review

### Spec coverage

- 任务页创建/编辑后自动排期生成提醒：Task 2
- 任务页重生成排期时旧提醒取消、新提醒生成：Task 2 + Task 5
- Agent 草稿确认后补提醒：Task 3
- 修改排期时对应提醒同步修改：Task 3
- 删除/失效排期时取消提醒：Task 3
- 提醒页只做前端折叠、不改后端存储：Task 4
- 折叠条件依赖 `source_task_id + status + remind_before_minutes + 本地 HH:mm`：Task 2 + Task 4
- 时区转换要求：File Structure 的 timezone invariants + Task 2/4/5

### Placeholder scan

- 无 `TODO` / `TBD`
- 每个任务都给了具体文件、命令、代码块、预期结果
- 前端没有强行引入新测试栈，保持仓库现状

### Type consistency

- 后端新字段统一命名为 `source_task_id`
- 后端同步入口统一命名为 `sync_pending_for_scheduled_item`
- 前端提醒类型统一命名为 `ReminderItem`
- 分组输出统一命名为 `ReminderDisplayNode`

