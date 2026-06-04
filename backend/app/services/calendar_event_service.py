from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CalendarEvent, EventStatus, ReminderTargetType, ScheduleSource
from app.services.channel_identity_service import ChannelIdentityService
from app.services.conflict_service import ConflictService
from app.services.reminder_service import ReminderService


class CalendarEventService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.reminders = ReminderService(db)
        self.conflicts = ConflictService(db)
        self.channel_identities = ChannelIdentityService(db)

    def create_event(
        self,
        *,
        user_id: str,
        title: str,
        description: str | None,
        start_time: datetime,
        end_time: datetime | None,
        timezone_name: str,
        location: str | None,
        remind_before_minutes: int | None,
        source: str = ScheduleSource.AGENT.value,
        created_by_channel: str | None = None,
    ) -> CalendarEvent:
        if end_time is None:
            end_time = start_time + timedelta(hours=1)
        event = CalendarEvent(
            user_id=user_id,
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone_name,
            location=location,
            source=source,
            created_by_channel=created_by_channel,
            remind_before_minutes=remind_before_minutes or 0,
        )
        self.db.add(event)
        self.db.flush()

        self.conflicts.detect_event_conflicts(user_id, event)
        trigger_time = start_time - timedelta(minutes=remind_before_minutes or 0)
        self.reminders.create_for_target(
            user_id=user_id,
            target_type=ReminderTargetType.EVENT.value,
            target_id=event.id,
            title=title,
            trigger_time=trigger_time,
        )
        return event

    def list_events(
        self,
        user_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        timezone_name: str = "Asia/Shanghai",
    ) -> list[CalendarEvent]:
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == EventStatus.ACTIVE.value,
        )
        if start_date is not None:
            local_tz = ZoneInfo(timezone_name)
            stmt = stmt.where(
                CalendarEvent.start_time >= datetime.combine(start_date, time.min, tzinfo=local_tz)
            )
        if end_date is not None:
            local_tz = ZoneInfo(timezone_name)
            stmt = stmt.where(
                CalendarEvent.start_time
                < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=local_tz)
            )
        return list(self.db.scalars(stmt.order_by(CalendarEvent.start_time.asc())))

    def get_event(self, user_id: str, event_id: str) -> CalendarEvent | None:
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.id == event_id,
            CalendarEvent.status == EventStatus.ACTIVE.value,
        )
        return self.db.scalar(stmt)

    def update_event(self, event: CalendarEvent, **changes: object) -> CalendarEvent:
        for key, value in changes.items():
            if value is not None:
                setattr(event, key, value)
        if event.end_time is None:
            event.end_time = event.start_time + timedelta(hours=1)
        self.reminders.cancel_by_target(user_id=event.user_id, target_id=event.id)
        self.reminders.create_for_target(
            user_id=event.user_id,
            target_type=ReminderTargetType.EVENT.value,
            target_id=event.id,
            title=event.title,
            trigger_time=event.start_time - timedelta(minutes=event.remind_before_minutes or 0),
        )
        return event

    def delete_event(self, event: CalendarEvent) -> CalendarEvent:
        event.status = EventStatus.DELETED.value
        self.reminders.cancel_by_target(user_id=event.user_id, target_id=event.id)
        return event

    def search_candidates(
        self,
        user_id: str,
        keyword: str,
        on_date: date | None = None,
        timezone_name: str = "Asia/Shanghai",
    ) -> list[CalendarEvent]:
        stmt = select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status == EventStatus.ACTIVE.value,
            (CalendarEvent.title.contains(keyword) | CalendarEvent.description.contains(keyword)),
        )
        if on_date is not None:
            local_tz = ZoneInfo(timezone_name)
            stmt = stmt.where(
                CalendarEvent.start_time >= datetime.combine(on_date, time.min, tzinfo=local_tz),
                CalendarEvent.start_time
                < datetime.combine(on_date + timedelta(days=1), time.min, tzinfo=local_tz),
            )
        return list(self.db.scalars(stmt.order_by(CalendarEvent.start_time.asc())))
