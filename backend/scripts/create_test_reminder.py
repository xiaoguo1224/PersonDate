"""创建测试日程和提醒"""
from datetime import datetime, timedelta, UTC
from app.db.session import SessionLocal
from app.models import User, CalendarEvent, ReminderJob, ReminderStatus
from sqlalchemy import select

db = SessionLocal()
try:
    user = db.scalar(select(User).where(User.role == "owner"))
    if not user:
        print("No owner found")
        exit(1)
    print(f"User: {user.id} ({user.display_name})")

    start = datetime.now(UTC) + timedelta(minutes=2)
    event = CalendarEvent(
        user_id=user.id,
        title="测试日程-提醒功能验证",
        date=start.date(),
        start_time=start,
        end_time=start + timedelta(hours=1),
        status="active",
    )
    db.add(event)
    db.flush()

    from app.models import ChannelIdentity
    identity = db.scalar(
        select(ChannelIdentity).where(
            ChannelIdentity.channel == "wechat",
            ChannelIdentity.user_id == user.id,
            ChannelIdentity.status == "active",
        )
    )

    reminder = ReminderJob(
        user_id=user.id,
        target_type="event",
        target_id=event.id,
        title=event.title,
        conversation_id=identity.conversation_id if identity else user.id,
        trigger_time=datetime.now(UTC) + timedelta(seconds=45),
        status=ReminderStatus.PENDING.value,
        max_retries=3,
    )
    db.add(reminder)
    db.commit()
    print(f"Event created: {event.id}")
    print(f"Reminder created: {reminder.id}, triggers in 45 seconds")
    print(f"Conversation: {reminder.conversation_id}")
finally:
    db.close()
