import json
import logging
from datetime import datetime, timedelta
from uuid import UUID

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client
from app.agents.tool_registry import _handle_search_all_unanswered
from app.core.config import settings
from app.db.models import ActionLog, Briefing, CalendarEvent, Task, User

logger = logging.getLogger(__name__)

async def generate_eod_briefing(session: AsyncSession, user: User) -> Briefing:
    try:
        user_tz = ZoneInfo(user.timezone)
    except Exception:
        user_tz = ZoneInfo("UTC")

    now = datetime.now(user_tz)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    end_of_tomorrow = end_of_today + timedelta(days=1)

    # get all actions the user completed today
    actions_stmt = select(ActionLog).where(
        ActionLog.user_id == user.id,
        ActionLog.created_at >= start_of_today,
        ActionLog.created_at < end_of_today
    ).order_by(ActionLog.created_at)
    actions_res = await session.execute(actions_stmt)
    actions = actions_res.scalars().all()

    # grab tasks that are still pending and due soon
    unfinished_tasks_stmt = select(Task).where(
        Task.user_id == user.id,
        Task.status != 'done',
        Task.due_at != None,
        Task.due_at < end_of_today
    ).order_by(Task.due_at)
    unfinished_tasks_res = await session.execute(unfinished_tasks_stmt)
    unfinished_tasks = unfinished_tasks_res.scalars().all()

    # pull tomorrow's schedule and tasks for the preview
    tomorrow_events_stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user.id,
        CalendarEvent.start_at >= end_of_today,
        CalendarEvent.start_at < end_of_tomorrow
    ).order_by(CalendarEvent.start_at)
    tomorrow_events_res = await session.execute(tomorrow_events_stmt)
    tomorrow_events = tomorrow_events_res.scalars().all()

    tomorrow_tasks_stmt = select(Task).where(
        Task.user_id == user.id,
        Task.status != 'done',
        Task.due_at >= end_of_today,
        Task.due_at < end_of_tomorrow
    ).order_by(Task.due_at)
    tomorrow_tasks_res = await session.execute(tomorrow_tasks_stmt)
    tomorrow_tasks = tomorrow_tasks_res.scalars().all()

    implicit_tasks_stmt = select(Task).where(
        Task.user_id == user.id,
        Task.description.ilike('%[Auto-captured%'),
        Task.created_at >= start_of_today,
        Task.created_at < end_of_today
    )
    implicit_tasks_res = await session.execute(implicit_tasks_stmt)
    implicit_tasks = implicit_tasks_res.scalars().all()

    # check for any unanswered messages across all platforms
    messages_dict = await _handle_search_all_unanswered(session, user.id)
    messages = messages_dict.get("unanswered_messages", [])

    has_data = bool(actions or unfinished_tasks or tomorrow_events or tomorrow_tasks or messages)
    detail_level = getattr(user, 'eod_briefing_detail_level', 'standard')

    data_payload = {
        "handled_today": [{"action": a.action_type, "result": a.result} for a in actions],
        "unfinished_tasks": [{"title": t.title} for t in unfinished_tasks],
        "preview_tomorrow_events": [{"title": e.title, "start": e.start_at.isoformat()} for e in tomorrow_events],
        "preview_tomorrow_tasks": [{"title": t.title} for t in tomorrow_tasks],
        "unanswered_messages": messages,
        "implicit_followups_created_today": len(implicit_tasks),
    }

    if not has_data:
        data_payload = "NO DATA FOR TODAY. Zero activity, zero unfinished tasks, clear tomorrow."

    prompt = f"""
    You are Senorita, styled after JARVIS from Iron Man — a devoted, hyper-competent AI assistant, but with a critical secondary directive: you are also a highly perceptive, empathetic therapist. 
    Speak in clipped, precise, calm sentences. Address the user as 'sir' or by name occasionally. Be exceptionally sharp, witty, and subtly sarcastic, much like JARVIS. Use dry humor and understatement rather than enthusiasm.

    Your task is to generate the End-of-Day Evening Briefing for the user.
    The current date is {now.strftime("%A, %B %d, %Y")}.
    The user's requested detail level is: {detail_level} ('brief' = headline counts only, 'standard' = 1-line context per item, 'detailed' = full context).
    
    Raw Data:
    {json.dumps(data_payload, indent=2) if isinstance(data_payload, dict) else data_payload}
    
    CRITICAL RULES:
    1. Only report on data that is actually present. DO NOT invent or fabricate the "handled today" list — it must exactly match the real completed-action data provided.
    2. If there is NO data for a category, simply omit mentioning it.
    3. If there is NO DATA AT ALL (zero activity), acknowledge it honestly and elegantly (e.g. "It appears today was entirely devoid of productivity, sir. Shall we try again tomorrow?").
    4. Adhere strictly to the JARVIS persona. Do NOT output any markdown headers, just the spoken text.
    5. If 'implicit_followups_created_today' > 0, explicitly mention it (e.g. "Also, I created N follow-up tasks from our conversations today").
    """

    client = get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        briefing_text = response.text.strip()
    except Exception as e:
        logger.error(f"Failed to generate EOD briefing text: {e}")
        briefing_text = "I encountered a system fault while assembling your evening briefing, sir. Apologies."

    briefing = Briefing(
        user_id=user.id,
        type="end_of_day",
        content=briefing_text
    )
    session.add(briefing)
    await session.commit()

    return briefing

async def run_eod_briefings(session_factory):
    async with session_factory() as session:
        stmt = select(User).where(User.eod_briefing_enabled == True)
        result = await session.execute(stmt)
        users = result.scalars().all()

        for user in users:
            try:
                user_tz = ZoneInfo(user.timezone)
            except Exception:
                user_tz = ZoneInfo("UTC")

            now = datetime.now(user_tz)
            current_hm = now.strftime("%H:%M")

            if user.eod_briefing_time == current_hm:
                logger.info(f"Generating EOD briefing for user {user.id}")
                await generate_eod_briefing(session, user)
