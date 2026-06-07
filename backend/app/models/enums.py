from enum import StrEnum


class UserRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class InviteCodeStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class ChannelType(StrEnum):
    WECHAT = "wechat"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class ContentType(StrEnum):
    TEXT = "text"


class ScheduledItemStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class ScheduledItemSource(StrEnum):
    MANUAL = "manual"
    AGENT = "agent"
    PLAN = "plan"


class EventStatus(StrEnum):
    ACTIVE = "active"
    DELETED = "deleted"


class ScheduleSource(StrEnum):
    AGENT = "agent"
    WEB = "web"
    WECHAT = "wechat"
    SYSTEM = "system"


class TaskScheduleType(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    DURATION_DAYS = "duration_days"
    CUSTOM_RANGE = "custom_range"


class TaskTimeType(StrEnum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class DayPlanStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    DELETED = "deleted"


class PlanItemStatus(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class PlanItemType(StrEnum):
    EVENT = "event"
    TASK = "task"
    BREAK = "break"
    OTHER = "other"


class ConflictType(StrEnum):
    TIME_OVERLAP = "time_overlap"
    TOO_MANY_TASKS = "too_many_tasks"
    DEADLINE_RISK = "deadline_risk"
    INSUFFICIENT_FREE_TIME = "insufficient_free_time"
    MISSING_TIME = "missing_time"
    AMBIGUOUS_INTENT = "ambiguous_intent"


class ConflictSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictStatus(StrEnum):
    OPEN = "open"
    IGNORED = "ignored"
    RESOLVED = "resolved"


class ReminderTargetType(StrEnum):
    SCHEDULED_ITEM = "scheduled_item"
    TASK = "task"
    OTHER = "other"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    FIRED = "fired"
    FAILED = "failed"
    CANCELED = "canceled"


class PendingStateType(StrEnum):
    WAITING_PLAN_CONFIRMATION = "waiting_plan_confirmation"
    WAITING_EVENT_SELECTION = "waiting_event_selection"
    WAITING_CONFLICT_RESOLUTION = "waiting_conflict_resolution"
    WAITING_CLARIFICATION = "waiting_clarification"
    WAITING_REMINDER_TIME = "waiting_reminder_time"
    WAITING_GENERIC_CONFIRMATION = "waiting_generic_confirmation"


class PendingStateStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"
    COMPLETED = "completed"
