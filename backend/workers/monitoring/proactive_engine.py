"""
workers/monitoring/proactive_engine.py

Polls every PROACTIVE_CHECK_INTERVAL_SECONDS (default 15 min) for events
that Señorita should surface without being asked.

Checks per active (non-paused) user:
  A. memory_entries with category='date', importance_score >= 0.3, locked=False
     that reference a date within the next PROACTIVE_WINDOW_DAYS days.
  B. tasks that are pending, due within 24 h, and have had no related
     action_log activity in the last 3 days.
  C. calendar_events with non-empty conflict_flags and surfaced=False.

Daily cap enforcement: max DAILY_NOTIFICATION_CAP notifications per user per day.
When the cap would be exceeded, lowest-importance candidates are skipped
(not marked processed) so they re-surface the next cycle after the cap resets.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, and_, cast
from sqlalchemy.dialects.postgresql import JSONB

from db.session import async_session_factory
from db.models import User, MemoryEntry, Task, CalendarEvent, ActionLog, NotificationLog
from workers.notifications.dispatch import dispatch_notification
from agents.tool_registry import _handle_search_all_unanswered
from agents.gemini_client import get_client
from core.config import settings
from core.state import get_pause_state

logger = logging.getLogger(__name__)

DAILY_CAP = settings.DAILY_NOTIFICATION_CAP
WINDOW_DAYS = settings.PROACTIVE_WINDOW_DAYS


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────

def _today_utc_range():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


async def _daily_count(session, user_id) -> int:
    start, end = _today_utc_range()
    result = await session.execute(
        select(func.count(NotificationLog.id)).where(
            and_(
                NotificationLog.user_id == user_id,
                NotificationLog.created_at >= start,
                NotificationLog.created_at < end,
            )
        )
    )
    return result.scalar() or 0


async def _log_and_dispatch(session, user_id, trigger_type: str, message: str, importance_score: float = 0.0):
    """Insert a NotificationLog row and dispatch to the desktop tray."""
    log_entry = NotificationLog(
        user_id=user_id,
        trigger_type=trigger_type,
        message=message,
        importance_score=importance_score,
        dispatched=True,
    )
    session.add(log_entry)
    await dispatch_notification(title="Señorita", message=message, payload={"trigger_type": trigger_type})


# ─────────────────────────────────────────────────────────
# Gemini helpers with graceful fallback when key is a placeholder
# ─────────────────────────────────────────────────────────

def _gemini_available() -> bool:
    try:
        client = get_client()
        key = getattr(client, "api_key", "") or ""
        return bool(key) and "your-gemini-api-key" not in key
    except Exception:
        return False


def _extract_date_from_content(content: str) -> datetime | None:
    """
    Ask Gemini to extract a calendar date from memory content.
    Falls back to a simple ISO-pattern regex when Gemini is unavailable.
    """
    if not _gemini_available():
        m = re.search(r'\d{4}-\d{2}-\d{2}', content)
        if m:
            try:
                return datetime.strptime(m.group(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    try:
        client = get_client()
        prompt = (
            "Extract the single most relevant calendar date from the text below. "
            "Reply ONLY with a date in YYYY-MM-DD format. "
            "If there is no specific date, reply with NONE.\n\n"
            f"Text: {content}"
        )
        resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=[prompt])
        raw = resp.text.strip()
        if raw.upper() == "NONE" or not raw:
            return None
        return datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception as e:
        logger.warning(f"Date extraction failed: {e}")
        return None


def _compose_notification(trigger_type: str, context_text: str, extra: str = "") -> str:
    """
    Ask Gemini to write an explicit, context-rich notification message.
    Falls back to a template when Gemini is unavailable.
    """
    if not _gemini_available():
        templates = {
            "memory_date": f"Upcoming date: {context_text}",
            "stalled_task": f"Task due soon with no recent activity: {context_text}",
            "calendar_conflict": f"Calendar conflict detected: {context_text}",
            "unanswered_message": f"Unanswered message pending for over 4 hours: {context_text}",
        }
        return templates.get(trigger_type, context_text)

    try:
        client = get_client()
        prompt = (
            "You are Señorita, a thoughtful personal AI assistant. "
            "Write a short, specific (1-2 sentence) proactive notification for the user. "
            "Be explicit about WHY you are surfacing this — never say just 'you have a reminder'. "
            "Reference exact details from the context. "
            f"Trigger type: {trigger_type}\n"
            f"Context: {context_text}\n"
            f"Extra: {extra or 'none'}\n\n"
            "Reply with ONLY the notification text."
        )
        resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=[prompt])
        return resp.text.strip()
    except Exception as e:
        logger.warning(f"Notification composition failed: {e}")
        return context_text


# ─────────────────────────────────────────────────────────
# Check A — memory date entries
# ─────────────────────────────────────────────────────────

async def _check_memory_dates(session, user: User) -> list[tuple]:
    """Returns list of (importance_score, trigger_type, message, post_fn)."""
    candidates = []
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=WINDOW_DAYS)

    result = await session.execute(
        select(MemoryEntry).where(
            and_(
                MemoryEntry.user_id == user.id,
                MemoryEntry.category == "date",
                MemoryEntry.locked == False,  # noqa: E712
                MemoryEntry.importance_score >= 0.3,
                MemoryEntry.status == "active",
            )
        )
    )
    entries = result.scalars().all()

    for entry in entries:
        target_date = _extract_date_from_content(entry.content)
        if target_date is None:
            continue
        if now <= target_date <= window_end:
            days_away = (target_date.date() - now.date()).days
            message = _compose_notification(
                trigger_type="memory_date",
                context_text=entry.content,
                extra=f"This date is {days_away} day(s) away.",
            )
            candidates.append((entry.importance_score or 0.3, "memory_date", message, None))

    return candidates


# ─────────────────────────────────────────────────────────
# Check B — stalled pending tasks
# ─────────────────────────────────────────────────────────

async def _check_stalled_tasks(session, user: User) -> list[tuple]:
    candidates = []
    now = datetime.now(timezone.utc)
    due_cutoff = now + timedelta(hours=24)
    activity_cutoff = now - timedelta(days=3)

    result = await session.execute(
        select(Task).where(
            and_(
                Task.user_id == user.id,
                Task.status == "pending",
                Task.due_at != None,  # noqa: E711
                Task.due_at >= now,
                Task.due_at <= due_cutoff,
            )
        )
    )
    tasks = result.scalars().all()

    for task in tasks:
        # Check for any recent action_log activity in the last 3 days
        recent = await session.execute(
            select(func.count(ActionLog.id)).where(
                and_(
                    ActionLog.user_id == user.id,
                    ActionLog.created_at >= activity_cutoff,
                    # Use payload text search as a heuristic for task linkage
                    func.cast(ActionLog.payload, JSONB).op("->>")(  # text of payload
                        "task_id"
                    ) == str(task.id),
                )
            )
        )
        if (recent.scalar() or 0) > 0:
            continue  # has recent activity, skip

        hours_left = round((task.due_at - now).total_seconds() / 3600, 1)
        message = _compose_notification(
            trigger_type="stalled_task",
            context_text=(
                f"Task '{task.title}' is due in {hours_left} hours "
                f"and hasn't had any recorded progress."
            ),
            extra=task.description or "",
        )
        priority_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
        importance = priority_map.get(task.priority or "medium", 0.6)
        candidates.append((importance, "stalled_task", message, None))

    return candidates


# ─────────────────────────────────────────────────────────
# Check C — unsurfaced calendar conflicts
# ─────────────────────────────────────────────────────────

async def _check_calendar_conflicts(session, user: User) -> list[tuple]:
    candidates = []

    result = await session.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.user_id == user.id,
                CalendarEvent.surfaced == False,  # noqa: E712
                cast(CalendarEvent.conflict_flags, JSONB) != cast("[]", JSONB),
            )
        )
    )
    events = result.scalars().all()

    for event in events:
        flags_text = ", ".join(str(f) for f in (event.conflict_flags or []))
        message = _compose_notification(
            trigger_type="calendar_conflict",
            context_text=(
                f"Event '{event.title}' on "
                f"{event.start_at.strftime('%b %d at %H:%M UTC')} "
                f"has conflicts: {flags_text}."
            ),
        )

        # Capture event reference for the closure
        _event = event
        async def mark_surfaced(session=session, ev=_event):
            ev.surfaced = True

        candidates.append((0.85, "calendar_conflict", message, mark_surfaced))

    return candidates


# ─────────────────────────────────────────────────────────
# Check D — Unanswered messages (> 4 hours)
# ─────────────────────────────────────────────────────────

async def _check_unanswered_messages(session, user: User) -> list[tuple]:
    candidates = []
    
    # Get unanswered messages using the tool registry helper
    messages_result = await _handle_search_all_unanswered(session, user.id)
    unanswered_list = messages_result.get("unanswered_messages", [])
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=4)
    
    for msg in unanswered_list:
        try:
            received_at = datetime.fromisoformat(msg["received_at"])
        except ValueError:
            continue
            
        if received_at < cutoff:
            # We don't have a specific `surfaced` flag on EmailMessage / SlackMessage for this.
            # However, the prompt says "that have been sitting unanswered longer than a configurable threshold".
            # To avoid spamming the same notification repeatedly, we rely on the daily cap,
            # or ideally we'd check if we already notified about this exact message.
            # Let's check NotificationLog to see if we've already surfaced this message today.
            
            # Simple deduplication: Check if there's a notification log for this message snippet in the last 12 hours.
            recent = await session.execute(
                select(func.count(NotificationLog.id)).where(
                    and_(
                        NotificationLog.user_id == user.id,
                        NotificationLog.trigger_type == "unanswered_message",
                        NotificationLog.created_at >= now - timedelta(hours=12),
                        NotificationLog.message.like(f"%{msg['from']}%") # simple heuristic
                    )
                )
            )
            if (recent.scalar() or 0) > 0:
                continue

            hours_waiting = round((now - received_at).total_seconds() / 3600, 1)
            message_text = _compose_notification(
                trigger_type="unanswered_message",
                context_text=(
                    f"Message from {msg['from']} via {msg['channel']} "
                    f"has been unanswered for {hours_waiting} hours.\n"
                    f"Snippet: {msg['snippet']}"
                )
            )
            
            candidates.append((0.6, "unanswered_message", message_text, None))

    return candidates


# ─────────────────────────────────────────────────────────
# Per-user dispatch with cap enforcement
# ─────────────────────────────────────────────────────────

async def _process_user(session, user: User):
    daily_count = await _daily_count(session, user.id)
    remaining_cap = DAILY_CAP - daily_count

    if remaining_cap <= 0:
        logger.info(f"User {user.id}: daily cap already reached ({DAILY_CAP}), skipping.")
        return

    all_candidates = []
    all_candidates.extend(await _check_memory_dates(session, user))
    all_candidates.extend(await _check_stalled_tasks(session, user))
    all_candidates.extend(await _check_calendar_conflicts(session, user))
    all_candidates.extend(await _check_unanswered_messages(session, user))

    if not all_candidates:
        logger.info(f"User {user.id}: no proactive candidates this cycle.")
        return

    # Sort descending by importance so highest-priority items dispatch first
    all_candidates.sort(key=lambda x: x[0], reverse=True)

    dispatched = 0
    skipped = 0
    for importance, trigger_type, message, post_fn in all_candidates:
        if dispatched >= remaining_cap:
            skipped += 1
            continue  # held for tomorrow — NOT marked processed

        await _log_and_dispatch(session, user.id, trigger_type, message, importance_score=importance)
        if post_fn:
            await post_fn()
        dispatched += 1
        logger.info(f"User {user.id} [{trigger_type}] importance={importance:.2f}: {message}")

    if skipped:
        logger.info(
            f"User {user.id}: cap hit — {skipped} candidate(s) held for next cycle."
        )


# ─────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────

async def proactive_check():
    """
    Top-level polling function — registered with APScheduler in main.py.
    Respects the global pause flag set by Module 7's /system/pause endpoint.
    """
    if get_pause_state():
        logger.info("Proactive engine: system paused, skipping cycle.")
        return

    logger.info("Proactive engine: starting check cycle.")
    async with async_session_factory() as session:
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()

        for user in users:
            try:
                await _process_user(session, user)
            except Exception as e:
                logger.error(f"Proactive engine error for user {user.id}: {e}", exc_info=True)

        await session.commit()

    logger.info("Proactive engine: cycle complete.")


def start_proactive_engine(scheduler):
    """
    Register proactive_check with the provided APScheduler instance.
    Called from main.py lifespan so the same scheduler object is shared
    with the reminder worker, keeping one consistent job registry.
    """
    scheduler.add_job(
        proactive_check,
        "interval",
        seconds=settings.PROACTIVE_CHECK_INTERVAL_SECONDS,
        id="proactive_engine",
        replace_existing=True,
    )
    logger.info(
        f"Proactive engine registered: interval={settings.PROACTIVE_CHECK_INTERVAL_SECONDS}s, "
        f"cap={DAILY_CAP}/day, window={WINDOW_DAYS} days."
    )
