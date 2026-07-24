from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo
from db.session import async_session_factory
from db.models import Reminder, User
from workers.notifications.dispatch import dispatch_notification
import logging
from core.state import get_pause_state
from integrations.token_refresh import refresh_expired_tokens

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

async def check_reminders():
    if get_pause_state():
        return
        
    async with async_session_factory() as session:
        stmt = select(Reminder).options(joinedload(Reminder.user)).where(Reminder.status == 'active')
        result = await session.execute(stmt)
        reminders = result.scalars().all()
        
        for reminder in reminders:
            try:
                # Default to UTC if user timezone is missing or invalid
                try:
                    user_tz = ZoneInfo(reminder.user.timezone)
                except Exception:
                    user_tz = ZoneInfo("UTC")
                
                now = datetime.now(user_tz)
                
                # Check trigger condition
                payload = reminder.trigger_payload or {}
                if reminder.type in ('time', 'date'):
                    trigger_dt_str = payload.get('datetime')
                    if not trigger_dt_str:
                        continue
                        
                    trigger_dt = datetime.fromisoformat(trigger_dt_str.replace("Z", "+00:00"))
                    # Make it timezone-aware if naive
                    if trigger_dt.tzinfo is None:
                        trigger_dt = trigger_dt.replace(tzinfo=user_tz)
                        
                    if now >= trigger_dt:
                        reminder.status = 'fired'
                        await dispatch_notification(
                            title="Reminder",
                            message=payload.get("note", "You have a reminder."),
                            payload=payload
                        )
            except Exception as e:
                logger.error(f"Error processing reminder {reminder.id}: {e}")
                
        await session.commit()

def start_scheduler_in_background():
    scheduler.add_job(check_reminders, 'interval', seconds=60)
    scheduler.add_job(refresh_expired_tokens, 'interval', minutes=30)
    scheduler.start()
    return scheduler  # expose so main.py can register additional jobs
