from typing import Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google.genai.types import FunctionDeclaration, Type, Tool

from db.models import Task, Reminder, CalendarEvent, MemoryEntry, Contact
from memory.embeddings import embed_text
from memory.retrieval import search_similar_memory
import json
from agents.gemini_client import start_chat

# Dummy functions for SDK schema extraction

def create_task(title: str, due_at: str = None, priority: str = None, project: str = None, contact_name: str = None):
    """Create a new task for the user. If contact_name is provided, it tries to link the task to an existing contact."""
    pass

def create_reminder(type: str, trigger_payload: dict):
    """Set a reminder for the user. Type is one of: time, date, recurring, event, context, location."""
    pass

def create_calendar_event(title: str, start_at: str, end_at: str, attendees: list[str] = None):
    """Add an event to the calendar. start_at and end_at must be ISO 8601 strings."""
    pass

def search_memory(query: str, category: str = None):
    """Search the user's memory for relevant facts, preferences, people, dates, or context."""
    pass

def store_memory(content: str, category: str, importance_score: float = None):
    """Save a new memory or fact about the user. Category must be one of: person, preference, date, promise, context."""
    pass

def find_contact(name: str):
    """Find a contact by fuzzy name matching."""
    pass

SENORITA_TOOLS = [
    create_task,
    create_reminder,
    create_calendar_event,
    search_memory,
    store_memory,
    find_contact,
]


# Python Implementations

async def execute_tool(session: AsyncSession, user_id: UUID, function_name: str, kwargs: dict) -> dict[str, Any]:
    handlers = {
        "create_task": _handle_create_task,
        "create_reminder": _handle_create_reminder,
        "create_calendar_event": _handle_create_calendar_event,
        "search_memory": _handle_search_memory,
        "store_memory": _handle_store_memory,
        "find_contact": _handle_find_contact,
    }
    handler = handlers.get(function_name)
    if not handler:
        return {"error": f"Unknown function {function_name}"}
    
    try:
        return await handler(session, user_id, **kwargs)
    except Exception as e:
        return {"error": str(e)}

async def _handle_create_task(session: AsyncSession, user_id: UUID, title: str, due_at: str = None, priority: str = None, project: str = None, contact_name: str = None) -> dict:
    contact_id = None
    if contact_name:
        # Fuzzy match
        stmt = select(Contact).where(Contact.user_id == user_id, Contact.name.ilike(f"%{contact_name}%"))
        result = await session.execute(stmt)
        contacts = result.scalars().all()
        if not contacts:
            return {"ambiguous": True, "suggested_name": contact_name, "error": f"No contact found matching '{contact_name}'. Please clarify."}
        if len(contacts) > 1:
            names = [c.name for c in contacts]
            return {"ambiguous": True, "suggested_name": contact_name, "error": f"Multiple contacts found: {names}. Please specify."}
        contact_id = contacts[0].id

    task_due = datetime.fromisoformat(due_at.replace("Z", "+00:00")) if due_at else None
    
    task = Task(
        user_id=user_id,
        title=title,
        due_at=task_due,
        priority=priority,
        project=project,
        contact_id=contact_id
    )
    session.add(task)
    # The orchestrator is responsible for committing and verifying success!
    # But here we just return the prospective task data. We can't rely on it having an ID until flush/commit.
    # To return a structured response, we flush it.
    await session.flush()
    return {"id": str(task.id), "title": task.title, "contact_id": str(contact_id) if contact_id else None}

async def _handle_create_reminder(session: AsyncSession, user_id: UUID, type: str, trigger_payload: dict) -> dict:
    reminder = Reminder(
        user_id=user_id,
        type=type,
        trigger_payload=trigger_payload
    )
    session.add(reminder)
    await session.flush()
    return {"id": str(reminder.id), "type": reminder.type}

async def _handle_create_calendar_event(session: AsyncSession, user_id: UUID, title: str, start_at: str, end_at: str, attendees: list[str] = None) -> dict:
    start_dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
    
    # Check for conflicts
    stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_at < end_dt,
        CalendarEvent.end_at > start_dt
    )
    result = await session.execute(stmt)
    conflicts = result.scalars().all()
    
    conflict_flags = []
    if conflicts:
        conflict_flags = [{"id": str(c.id), "title": c.title, "start_at": c.start_at.isoformat(), "end_at": c.end_at.isoformat()} for c in conflicts]
    
    event = CalendarEvent(
        user_id=user_id,
        title=title,
        start_at=start_dt,
        end_at=end_dt,
        attendees=attendees or [],
        conflict_flags=conflict_flags
    )
    session.add(event)
    await session.flush()
    
    resp = {"id": str(event.id), "title": event.title}
    if conflict_flags:
        resp["conflict_info"] = conflict_flags
    return resp

async def _handle_search_memory(session: AsyncSession, user_id: UUID, query: str, category: str = None) -> dict:
    query_embedding = await embed_text(query, task_type="RETRIEVAL_QUERY")
    results = await search_similar_memory(session, user_id, query_embedding, top_k=5)
    
    if category:
        results = [r for r in results if r.category == category]
        
    return {
        "hits": [{"content": r.content, "category": r.category, "created_at": r.created_at.isoformat()} for r in results]
    }

async def _handle_store_memory(session: AsyncSession, user_id: UUID, content: str, category: str, importance_score: float = None) -> dict:
    if importance_score is None:
        prompt = f"Score the importance of this fact from 0.0 to 1.0, and provide a 1-line justification. Fact: '{content}'. Return ONLY a JSON object with 'score' (float) and 'justification' (string)."
        try:
            chat = start_chat()
            response = await chat.send_message(prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
            data = json.loads(text)
            importance_score = float(data.get("score", 0.5))
        except Exception:
            importance_score = 0.5

    embedding = await embed_text(content, task_type="RETRIEVAL_DOCUMENT")
    
    # NOTE: Entries with importance_score < 0.3 must be excluded from future proactive-surfacing logic.
    mem = MemoryEntry(
        user_id=user_id,
        content=content,
        category=category,
        importance_score=importance_score,
        embedding=embedding
    )
    session.add(mem)
    await session.flush()
    return {"id": str(mem.id), "content": mem.content, "importance_score": importance_score}

async def _handle_find_contact(session: AsyncSession, user_id: UUID, name: str) -> dict:
    stmt = select(Contact).where(Contact.user_id == user_id, Contact.name.ilike(f"%{name}%"))
    result = await session.execute(stmt)
    contacts = result.scalars().all()
    
    if not contacts:
        return {"ambiguous": True, "suggested_name": name, "error": f"No contact found matching '{name}'. Please clarify if this is a new person."}
    
    if len(contacts) > 1:
        names = [c.name for c in contacts]
        return {"ambiguous": True, "suggested_name": name, "error": f"Multiple contacts found: {names}. Please specify."}

    return {
        "contact": [
            {"id": str(c.id), "name": c.name, "relationship_type": c.relationship_type} 
            for c in contacts
        ]
    }
