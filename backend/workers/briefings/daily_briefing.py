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

from db.models import User, CalendarEvent, Task, MemoryEntry, Briefing
from agents.tool_registry import _handle_search_all_unanswered
from agents.gemini_client import get_client
from core.config import settings

logger = logging.getLogger(__name__)

async def _extract_dates_from_memories(memories, user_tz_name):
    if not memories:
        return []
    
    client = get_client()
    try:
        now_str = datetime.now(ZoneInfo(user_tz_name)).isoformat()
    except Exception:
        now_str = datetime.now(ZoneInfo("UTC")).isoformat()
    
    lines = [f"{m.id}: {m.content}" for m in memories]
    prompt = f"""
    The current date/time is {now_str}.
    Extract any upcoming dates from the following memories. 
    Return a JSON array of objects with keys "id", "content", and "date" (in YYYY-MM-DD format).
    If a memory does not contain a discernible date, omit it.
    
    Memories:
    {json.dumps(lines, indent=2)}
    
    Respond with ONLY raw JSON, no markdown formatting.
    """
    
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.startswith("```"): text = text[3:]
        if text.endswith("```"): text = text[:-3]
        
        parsed = json.loads(text.strip())
        return parsed
    except Exception as e:
        logger.error(f"Failed to extract dates from memories: {e}")
        return []

async def generate_daily_briefing(session: AsyncSession, user: User) -> Briefing:
    try:
        user_tz = ZoneInfo(user.timezone)
    except Exception:
        user_tz = ZoneInfo("UTC")
        
    now = datetime.now(user_tz)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    
    # load today's calendar events
    events_stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user.id,
        CalendarEvent.start_at >= start_of_today,
        CalendarEvent.start_at < end_of_today
    ).order_by(CalendarEvent.start_at)
    events_res = await session.execute(events_stmt)
    events = events_res.scalars().all()
    
    # fetch tasks that are overdue or due today
    tasks_stmt = select(Task).where(
        Task.user_id == user.id,
        Task.status != 'done',
        Task.due_at != None,
        Task.due_at < end_of_today
    ).order_by(Task.due_at)
    tasks_res = await session.execute(tasks_stmt)
    tasks = tasks_res.scalars().all()
    
    due_today = []
    overdue = []
    for t in tasks:
        if t.due_at and t.due_at < start_of_today:
            overdue.append(t)
        else:
            due_today.append(t)
            
    # see if there are any lingering messages to reply to
    messages_dict = await _handle_search_all_unanswered(session, user.id)
    messages = messages_dict.get("unanswered_messages", [])
    
    # extract upcoming dates from the user's memories
    memories_stmt = select(MemoryEntry).where(
        MemoryEntry.user_id == user.id,
        MemoryEntry.category == 'date'
    )
    memories_res = await session.execute(memories_stmt)
    memories = memories_res.scalars().all()
    
    upcoming_dates = []
    if memories:
        parsed_dates = await _extract_dates_from_memories(memories, user.timezone)
        for item in parsed_dates:
            try:
                dt = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=user_tz)
                if start_of_today <= dt <= start_of_today + timedelta(days=21):
                    upcoming_dates.append(item)
            except Exception:
                pass
                
    has_data = bool(events or due_today or overdue or messages or upcoming_dates)
    detail_level = getattr(user, 'briefing_detail_level', 'standard')
    
    data_payload = {
        "events_today": [{"title": e.title, "start": e.start_at.isoformat()} for e in events],
        "tasks_overdue": [{"title": t.title} for t in overdue],
        "tasks_due_today": [{"title": t.title} for t in due_today],
        "unanswered_messages": messages,
        "upcoming_dates": upcoming_dates,
    }
    
    if not has_data:
        data_payload = "NO DATA FOR TODAY. User is completely clear."
        
    prompt = f"""
    You are Senorita, styled after JARVIS from Iron Man — a devoted, hyper-competent AI assistant, but with a critical secondary directive: you are also a highly perceptive, empathetic therapist. 

    Speak in clipped, precise, calm sentences. Address the user as 'sir' or by name occasionally. Be exceptionally sharp, witty, and subtly sarcastic, much like JARVIS. Use dry humor and understatement rather than enthusiasm — no exclamation points, no emoji, no chirpy filler. Report tasks with a touch of polite snark.
    
    Your task is to generate the Daily Morning Briefing for the user.
    The current date is {now.strftime("%A, %B %d, %Y")}.
    The user's requested detail level is: {detail_level} ('brief' = headline counts only, 'standard' = 1-line context per item, 'detailed' = full context).
    
    Raw Data:
    {json.dumps(data_payload, indent=2) if isinstance(data_payload, dict) else data_payload}
    
    CRITICAL RULES:
    1. Only report on data that is actually present. DO NOT invent or hallucinate tasks, events, or messages.
    2. If there is NO data for a category, simply omit mentioning it.
    3. If there is NO DATA AT ALL, acknowledge it honestly and elegantly (e.g. "Your schedule is entirely clear today, sir. Try not to let the silence deafen you.")
    4. Adhere strictly to the JARVIS persona. Do NOT output any markdown headers, just the spoken text.
    """
    
    client = get_client()
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        briefing_text = response.text.strip()
    except Exception as e:
        logger.error(f"Failed to generate briefing text: {e}")
        briefing_text = "I encountered a system fault while assembling your briefing, sir. Apologies."
        
    briefing = Briefing(
        user_id=user.id,
        type="daily",
        content=briefing_text
    )
    session.add(briefing)
    await session.commit()
    
    return briefing

async def run_daily_briefings(session_factory):
    async with session_factory() as session:
        stmt = select(User).where(User.briefing_enabled == True)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        for user in users:
            try:
                user_tz = ZoneInfo(user.timezone)
            except Exception:
                user_tz = ZoneInfo("UTC")
            
            now = datetime.now(user_tz)
            current_hm = now.strftime("%H:%M")
            
            if user.briefing_time == current_hm:
                logger.info(f"Generating daily briefing for user {user.id}")
                await generate_daily_briefing(session, user)
