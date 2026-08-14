import difflib
import logging
import os
import platform
import subprocess
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from google.genai.types import FunctionDeclaration, Tool, Type
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import base64
import json
from email.message import EmailMessage as PyEmailMessage

import httpx
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.agents.gemini_client import get_client, start_chat
from app.core.crypto import decrypt
from app.db.models import (
    ActionLog,
    CalendarEvent,
    Contact,
    EmailMessage,
    Integration,
    MemoryEntry,
    Reminder,
    SlackMessage,
    Task,
    User,
)
from app.integrations.base import get_adapter
from app.memory.embeddings import embed_text
from app.memory.retrieval import search_similar_memory
from app.services.message_mode_service import resolve_mode

# Dummy functions for SDK schema extraction

def create_task(title: str, due_at: Optional[str] = None, priority: Optional[str] = None, project: Optional[str] = None, contact_name: Optional[str] = None):
    """Create a new task for the user. If due_at is omitted it has no deadline. If contact_name is provided, it tries to link the task to an existing contact."""
    pass

def create_reminder(type: str, trigger_payload: dict):
    """Set a reminder for the user. Type is one of: time, date, recurring, event, context, location."""
    pass

def create_calendar_event(title: str, start_at: str, end_at: str, attendees: Optional[list[str]] = None):
    """Add an event to the calendar. start_at and end_at must be ISO 8601 strings."""
    pass

def read_calendar_events(date: Optional[str] = None, limit: Optional[int] = None):
    """Read the user's calendar events. If date is provided, use YYYY-MM-DD and return that day's events; otherwise returns today's events. Includes manually-created and synced Google Calendar events."""
    pass

def search_memory(query: str, category: Optional[str] = None):
    """Search the user's memory for relevant facts, preferences, people, dates, or context."""
    pass

def store_memory(content: str, category: str, importance_score: Optional[float] = None):
    """Save a new memory or fact about the user. Category must be one of: person, preference, date, promise, context."""
    pass

def find_contact(name: str):
    """Find a contact by fuzzy name matching."""
    pass

def read_emails(filter: Optional[str], limit: Optional[int]):
    """Read emails from the database. Filter can be 'unread', 'needs_reply', or a sender's email/name. Limit defaults to 10 if omitted."""
    pass

def summarize_email(email_id: str):
    """Fetch the full email body live from Gmail and summarize it using Gemini."""
    pass

def draft_email_reply(email_id: str, intent: str):
    """Draft a reply to a specific email and save it in the user's Gmail Drafts."""
    pass

def send_email(draft_id: str):
    """Send an existing email draft from Gmail."""
    pass

def read_slack_messages(filter: Optional[str] = None, limit: Optional[int] = None):
    """Read messages from Slack. Filter can be 'needs_reply', a channel ID/name, or a sender's Slack user ID. Limit defaults to 10."""
    pass

def draft_slack_reply(channel_id: str, intent: str):
    """Draft a reply for a Slack channel or DM and return the proposed text for review."""
    pass

def send_slack_message(channel_id: str, message: str):
    """Send a message to a Slack channel or DM using the connected Slack bot."""
    pass

def search_all_unanswered():
    """Search for unanswered messages across all connected channels (Gmail, Slack)."""
    pass

def get_pc_stats():
    """Get current PC hardware statistics including CPU, Memory, and Disk usage."""
    pass

def open_application(app_name: str):
    """Open or launch an application on the user's computer. Pass a simple app name like 'vs code', 'chrome', 'spotify', 'notepad', 'terminal', 'file explorer', 'calculator', 'discord', 'slack', 'firefox'."""
    pass

def analyze_repository(path: str):
    """Analyze a code repository at the given file system path and provide a structured overview of its tech stack, architecture, file structure, dependencies, and suggested starting points for understanding the code. The path must be an absolute path to a directory on the user's machine."""
    pass

SENORITA_TOOLS = [
    create_task,
    create_reminder,
    create_calendar_event,
    read_calendar_events,
    search_memory,
    store_memory,
    find_contact,
    read_emails,
    summarize_email,
    draft_email_reply,
    send_email,
    read_slack_messages,
    draft_slack_reply,
    send_slack_message,
    search_all_unanswered,
    get_pc_stats,
    open_application,
    analyze_repository,
]


# Python Implementations

async def execute_tool(session: AsyncSession, user_id: UUID, function_name: str, kwargs: dict) -> dict[str, Any]:
    handlers = {
        "create_task": _handle_create_task,
        "create_reminder": _handle_create_reminder,
        "create_calendar_event": _handle_create_calendar_event,
        "read_calendar_events": _handle_read_calendar_events,
        "search_memory": _handle_search_memory,
        "store_memory": _handle_store_memory,
        "find_contact": _handle_find_contact,
        "read_emails": _handle_read_emails,
        "summarize_email": _handle_summarize_email,
        "draft_email_reply": _handle_draft_email_reply,
        "send_email": _handle_send_email,
        "read_slack_messages": _handle_read_slack_messages,
        "draft_slack_reply": _handle_draft_slack_reply,
        "send_slack_message": _handle_send_slack_message,
        "search_all_unanswered": _handle_search_all_unanswered,
        "get_pc_stats": _handle_get_pc_stats,
        "open_application": _handle_open_application,
        "analyze_repository": _handle_analyze_repository,
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
        conflict_flags = [
            {
                "id": str(c.id),
                "title": c.title,
                "source": c.source,
                "start_at": c.start_at.isoformat(),
                "end_at": c.end_at.isoformat(),
            }
            for c in conflicts
        ]

    event = CalendarEvent(
        user_id=user_id,
        title=title,
        start_at=start_dt,
        end_at=end_dt,
        attendees=attendees or [],
        source="manual",
        source_calendar="local",
        conflict_flags=conflict_flags
    )
    session.add(event)
    await session.flush()

    resp = {"id": str(event.id), "title": event.title}
    if conflict_flags:
        resp["conflict_info"] = conflict_flags
    return resp

async def _handle_read_calendar_events(session: AsyncSession, user_id: UUID, date: str = None, limit: int = None) -> dict:
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    try:
        user_tz = ZoneInfo(user.timezone if user else "UTC")
    except Exception:
        user_tz = ZoneInfo("UTC")

    if date:
        day = datetime.fromisoformat(date.replace("Z", "+00:00")).date()
    else:
        day = datetime.now(user_tz).date()

    start_dt = datetime.combine(day, time.min, tzinfo=user_tz)
    end_dt = start_dt + timedelta(days=1)

    stmt = (
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_at < end_dt,
            CalendarEvent.end_at > start_dt,
        )
        .order_by(CalendarEvent.start_at)
    )
    if limit:
        stmt = stmt.limit(limit)

    result = await session.execute(stmt)
    events = result.scalars().all()

    return {
        "date": day.isoformat(),
        "events": [
            {
                "id": str(event.id),
                "title": event.title,
                "source": event.source,
                "start_at": event.start_at.isoformat(),
                "end_at": event.end_at.isoformat(),
                "attendees": event.attendees,
                "conflict_flags": event.conflict_flags,
            }
            for event in events
        ],
    }

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

def _get_gmail_service(integration: Integration):
    access_token = decrypt(integration.access_token_encrypted)
    creds = Credentials(token=access_token)
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)

async def _handle_read_emails(session: AsyncSession, user_id: UUID, filter: str = "unread", limit: int = 10) -> dict:
    stmt = select(EmailMessage).where(EmailMessage.user_id == user_id)
    if filter == "unread":
        stmt = stmt.where(EmailMessage.is_read == False)
    elif filter == "needs_reply":
        stmt = stmt.where(EmailMessage.needs_reply == True)
    else:
        # Assuming filter is a sender name/email
        stmt = stmt.where(EmailMessage.from_address.ilike(f"%{filter}%"))

    stmt = stmt.order_by(EmailMessage.received_at.desc()).limit(limit)
    result = await session.execute(stmt)
    emails = result.scalars().all()

    return {
        "emails": [
            {
                "id": str(e.id),
                "gmail_message_id": e.gmail_message_id,
                "from": e.from_address,
                "subject": e.subject,
                "snippet": e.snippet,
                "received_at": e.received_at.isoformat(),
                "needs_reply": e.needs_reply
            } for e in emails
        ]
    }

async def _handle_summarize_email(session: AsyncSession, user_id: UUID, email_id: str) -> dict:
    email = await session.get(EmailMessage, email_id)
    if not email:
        return {"error": "Email not found."}

    integration = (await session.execute(select(Integration).where(Integration.user_id == user_id, Integration.provider == "gmail"))).scalars().first()
    if not integration or integration.status != "connected":
        return {"error": "Gmail not connected."}

    try:
        import asyncio
        service = _get_gmail_service(integration)
        msg_data = await asyncio.to_thread(lambda: service.users().messages().get(userId='me', id=email.gmail_message_id, format='full').execute())

        # Decode body
        body = ""
        if 'parts' in msg_data['payload']:
            for part in msg_data['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    break
        elif 'body' in msg_data['payload'] and 'data' in msg_data['payload']['body']:
             body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8')

        client = get_client()
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[f"Summarize this email in a few concise sentences:\n\n{body}"]
        )
        return {"summary": resp.text.strip(), "original_snippet": email.snippet}
    except Exception as e:
        return {"error": str(e)}

async def _handle_draft_email_reply(session: AsyncSession, user_id: UUID, email_id: str, intent: str) -> dict:
    email = await session.get(EmailMessage, email_id)
    if not email:
        return {"error": "Email not found."}

    integration = (await session.execute(select(Integration).where(Integration.user_id == user_id, Integration.provider == "gmail"))).scalars().first()
    if not integration or integration.status != "connected":
        return {"error": "Gmail not connected."}

    if not integration.permissions.get("draft", False):
        return {"error": "Permission 'draft' is not enabled for Gmail."}

    try:
        client = get_client()

        # Determine Tone Profile
        tone_instructions = ""
        stmt = select(Contact).where(Contact.user_id == user_id)
        contacts = (await session.execute(stmt)).scalars().all()
        target_contact = None
        for c in contacts:
            if c.name.lower() in email.from_address.lower():
                target_contact = c
                break

        if target_contact and "email" in target_contact.tone_profile:
            tp = target_contact.tone_profile["email"]
            style = tp.get("style", {})
            tone_instructions = (
                f"\n\nTONE INSTRUCTIONS (Match the user's natural style for this contact):\n"
                f"- Formality: {style.get('formality', 'neutral')}\n"
                f"- Emoji use: {style.get('emoji', 'occasional')}\n"
                f"- Sentence length: {style.get('sentence_length', 'medium')}\n"
                f"- Punctuation: {style.get('punctuation', 'standard')}\n"
                f"- Uses exclamation marks: {style.get('uses_exclamation', False)}\n"
                f"- Uses lowercase strictly: {style.get('uses_lowercase', False)}\n"
                f"- Abbreviations: {', '.join(style.get('uses_abbreviations', []))}\n"
            )
            if tp.get("greeting_examples"):
                tone_instructions += f"- Example greetings they use: {', '.join(tp['greeting_examples'])}\n"
            if tp.get("closing_examples"):
                tone_instructions += f"- Example closings they use: {', '.join(tp['closing_examples'])}\n"
            if tp.get("reusable_patterns"):
                pats = [p.get("template") for p in tp["reusable_patterns"]]
                tone_instructions += f"- Reusable phrasing patterns they use: {', '.join(pats)}\n"

        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[f"Draft a reply to the email '{email.subject}' from '{email.from_address}'.\nIntent: {intent}\nSnippet: {email.snippet}{tone_instructions}\n\nReturn ONLY the email body text."]
        )
        draft_text = resp.text.strip()

        message = PyEmailMessage()
        message.set_content(draft_text)
        message['To'] = email.from_address
        message['Subject'] = f"Re: {email.subject}"
        message['In-Reply-To'] = email.gmail_message_id
        message['References'] = email.gmail_message_id

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'message': {'raw': encoded_message}}

        import asyncio
        service = _get_gmail_service(integration)
        draft = await asyncio.to_thread(lambda: service.users().drafts().create(userId='me', body=create_message).execute())

        return {"draft_id": draft['id'], "content": draft_text}
    except Exception as e:
        return {"error": str(e)}

async def _handle_send_email(session: AsyncSession, user_id: UUID, draft_id: str) -> dict:
    integration = (await session.execute(select(Integration).where(Integration.user_id == user_id, Integration.provider == "gmail"))).scalars().first()
    if not integration or integration.status != "connected":
        return {"error": "Gmail not connected."}

    # Find draft email from our DB (if it exists) to try and find contact
    # Actually, we don't store drafts in DB right now, we just pass ID.
    # In a full implementation, we'd parse the draft from Gmail to get the recipient.

    # We resolve the mode for the channel
    mode = await resolve_mode(session, user_id, None, "gmail")

    if mode in ("draft_only", "approval_required"):
        return {
            "error": "confirmation_required",
            "detail": f"Message mode is {mode}. Please confirm before sending."
        }

    try:
        import asyncio
        service = _get_gmail_service(integration)
        sent_message = await asyncio.to_thread(lambda: service.users().drafts().send(userId='me', body={'id': draft_id}).execute())

        # Log success strictly as required
        log = ActionLog(
            user_id=user_id,
            action_type="send_email",
            payload={"draft_id": draft_id},
            result="success",
            confirmed_by_user=False
        )
        session.add(log)
        await session.flush()

        return {"status": "success", "message_id": sent_message['id']}
    except Exception as e:
        log = ActionLog(
            user_id=user_id,
            action_type="send_email",
            payload={"draft_id": draft_id},
            result="failed",
            confirmed_by_user=False
        )
        session.add(log)
        await session.flush()
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Slack handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_slack_integration(session: AsyncSession, user_id: UUID) -> Integration | None:
    result = await session.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == "slack",
            Integration.status == "connected",
        )
    )
    return result.scalars().first()


async def _handle_read_slack_messages(
    session: AsyncSession, user_id: UUID, filter: str = "needs_reply", limit: int = 10
) -> dict:
    stmt = select(SlackMessage).where(SlackMessage.user_id == user_id)

    if filter == "needs_reply":
        stmt = stmt.where(SlackMessage.needs_reply == True)
    elif filter:
        # Could be a channel_id, channel_name, or from_user partial match
        stmt = stmt.where(
            or_(
                SlackMessage.slack_channel_id == filter,
                SlackMessage.channel_name.ilike(f"%{filter}%"),
                SlackMessage.from_user.ilike(f"%{filter}%"),
            )
        )

    stmt = stmt.order_by(SlackMessage.received_at.desc()).limit(limit)
    result = await session.execute(stmt)
    messages = result.scalars().all()

    return {
        "messages": [
            {
                "id": str(m.id),
                "channel_id": m.slack_channel_id,
                "channel_name": m.channel_name,
                "from_user": m.from_user,
                "snippet": m.body_snippet,
                "received_at": m.received_at.isoformat(),
                "needs_reply": m.needs_reply,
                "ts": m.slack_message_ts,
            }
            for m in messages
        ]
    }


async def _handle_draft_slack_reply(
    session: AsyncSession, user_id: UUID, channel_id: str, intent: str
) -> dict:
    """
    Generates a draft reply for the given Slack channel using the AI and returns
    the proposed text. Does NOT post to Slack — requires an explicit send_slack_message call.
    """
    # Fetch recent messages from this channel for context
    context_result = await session.execute(
        select(SlackMessage)
        .where(SlackMessage.user_id == user_id, SlackMessage.slack_channel_id == channel_id)
        .order_by(SlackMessage.received_at.desc())
        .limit(5)
    )
    context_messages = context_result.scalars().all()
    context_text = "\n".join(
        [f"{m.from_user}: {m.body_snippet}" for m in reversed(context_messages)]
    )

    try:
        client = get_client()
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                f"Draft a Slack reply for the following conversation.\n"
                f"Intent: {intent}\n\n"
                f"Recent messages:\n{context_text}\n\n"
                f"Return ONLY the message text, no extra commentary."
            ],
        )
        draft_text = resp.text.strip()
        return {"channel_id": channel_id, "draft": draft_text}
    except Exception as e:
        return {"error": str(e)}


async def _handle_send_slack_message(
    session: AsyncSession, user_id: UUID, channel_id: str, message: str
) -> dict:
    """
    Posts a message to a Slack channel/DM via the Slack Web API chat.postMessage.
    Gated by the send_automatically permission on the Slack integration.
    """
    integration = await _get_slack_integration(session, user_id)
    if not integration:
        return {"error": "Slack not connected."}

    # Resolve message mode
    # Ideally we'd map channel_id to a contact if it's a DM, but we'll use channel default for now.
    mode = await resolve_mode(session, user_id, None, "slack")

    if mode in ("draft_only", "approval_required"):
        return {
            "error": "confirmation_required",
            "detail": f"Message mode is {mode} for Slack. Please confirm before sending.",
            "draft": message,
            "channel_id": channel_id,
        }

    access_token = decrypt(integration.access_token_encrypted)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"channel": channel_id, "text": message},
            )
            data = resp.json()

        if not data.get("ok"):
            raise ValueError(f"Slack API error: {data.get('error')}")

        log = ActionLog(
            user_id=user_id,
            action_type="send_slack_message",
            payload={"channel_id": channel_id},
            result="success",
            confirmed_by_user=False,
        )
        session.add(log)
        await session.flush()

        return {"status": "sent", "ts": data.get("ts"), "channel": channel_id}

    except Exception as e:
        log = ActionLog(
            user_id=user_id,
            action_type="send_slack_message",
            payload={"channel_id": channel_id},
            result="failed",
            confirmed_by_user=False,
        )
        session.add(log)
        await session.flush()
        return {"error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# Cross-channel handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_search_all_unanswered(session: AsyncSession, user_id: UUID) -> dict:
    # Get unanswered emails
    email_stmt = select(EmailMessage).where(
        EmailMessage.user_id == user_id,
        EmailMessage.needs_reply == True
    ).order_by(EmailMessage.received_at.desc())
    email_res = await session.execute(email_stmt)
    emails = email_res.scalars().all()

    # Get unanswered Slack messages
    slack_stmt = select(SlackMessage).where(
        SlackMessage.user_id == user_id,
        SlackMessage.needs_reply == True
    ).order_by(SlackMessage.received_at.desc())
    slack_res = await session.execute(slack_stmt)
    slacks = slack_res.scalars().all()

    results = []
    for e in emails:
        results.append({
            "channel": "gmail",
            "id": str(e.id),
            "from": e.from_address,
            "snippet": e.snippet,
            "received_at": e.received_at.isoformat()
        })

    for s in slacks:
        results.append({
            "channel": "slack",
            "id": str(s.id),
            "from": s.from_user,
            "snippet": s.body_snippet,
            "received_at": s.received_at.isoformat()
        })

    # Sort by received_at desc
    results.sort(key=lambda x: x["received_at"], reverse=True)

    return {"unanswered_messages": results}

async def _handle_get_pc_stats(session: AsyncSession, user_id: UUID) -> dict:
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }


# ─────────────────────────────────────────────────────────────────────────────
# App Launcher
# ─────────────────────────────────────────────────────────────────────────────

_log = logging.getLogger("senorita.tools")

# Common app name aliases → launch commands (Windows-focused, with macOS fallbacks)
_APP_ALIASES: dict[str, dict[str, list[str]]] = {
    # ── IDEs & editors ──
    "vs code":            {"Windows": ["code"], "Darwin": ["open", "-a", "Visual Studio Code"]},
    "vscode":             {"Windows": ["code"], "Darwin": ["open", "-a", "Visual Studio Code"]},
    "visual studio code": {"Windows": ["code"], "Darwin": ["open", "-a", "Visual Studio Code"]},
    "cursor":             {"Windows": ["cursor"], "Darwin": ["open", "-a", "Cursor"]},
    "sublime":            {"Windows": ["subl"], "Darwin": ["open", "-a", "Sublime Text"]},
    "sublime text":       {"Windows": ["subl"], "Darwin": ["open", "-a", "Sublime Text"]},
    "notepad":            {"Windows": ["notepad"], "Darwin": ["open", "-a", "TextEdit"]},
    "notepad++":          {"Windows": ["cmd", "/c", "start", "notepad++"], "Darwin": ["open", "-a", "TextEdit"]},
    # ── Browsers ──
    "chrome":             {"Windows": ["cmd", "/c", "start", "chrome"], "Darwin": ["open", "-a", "Google Chrome"]},
    "google chrome":      {"Windows": ["cmd", "/c", "start", "chrome"], "Darwin": ["open", "-a", "Google Chrome"]},
    "firefox":            {"Windows": ["cmd", "/c", "start", "firefox"], "Darwin": ["open", "-a", "Firefox"]},
    "brave":              {"Windows": ["cmd", "/c", "start", "brave"], "Darwin": ["open", "-a", "Brave Browser"]},
    "edge":               {"Windows": ["cmd", "/c", "start", "msedge"], "Darwin": ["open", "-a", "Microsoft Edge"]},
    "microsoft edge":     {"Windows": ["cmd", "/c", "start", "msedge"], "Darwin": ["open", "-a", "Microsoft Edge"]},
    # ── Terminals ──
    "terminal":           {"Windows": ["wt"], "Darwin": ["open", "-a", "Terminal"]},
    "windows terminal":   {"Windows": ["wt"], "Darwin": ["open", "-a", "Terminal"]},
    "powershell":         {"Windows": ["powershell"], "Darwin": ["open", "-a", "Terminal"]},
    "cmd":                {"Windows": ["cmd"], "Darwin": ["open", "-a", "Terminal"]},
    "command prompt":     {"Windows": ["cmd"], "Darwin": ["open", "-a", "Terminal"]},
    "git bash":           {"Windows": ["cmd", "/c", "start", "", "git-bash.exe"], "Darwin": ["open", "-a", "Terminal"]},
    # ── Communication ──
    "spotify":            {"Windows": ["cmd", "/c", "start", "spotify:"], "Darwin": ["open", "-a", "Spotify"]},
    "discord":            {"Windows": ["cmd", "/c", "start", "discord:"], "Darwin": ["open", "-a", "Discord"]},
    "slack":              {"Windows": ["cmd", "/c", "start", "slack:"], "Darwin": ["open", "-a", "Slack"]},
    "telegram":           {"Windows": ["cmd", "/c", "start", "tg:"], "Darwin": ["open", "-a", "Telegram"]},
    "whatsapp":           {"Windows": ["cmd", "/c", "start", "whatsapp:"], "Darwin": ["open", "-a", "WhatsApp"]},
    "zoom":               {"Windows": ["cmd", "/c", "start", "zoommtg:"], "Darwin": ["open", "-a", "zoom.us"]},
    "teams":              {"Windows": ["cmd", "/c", "start", "msteams:"], "Darwin": ["open", "-a", "Microsoft Teams"]},
    "microsoft teams":    {"Windows": ["cmd", "/c", "start", "msteams:"], "Darwin": ["open", "-a", "Microsoft Teams"]},
    # ── Productivity ──
    "word":               {"Windows": ["cmd", "/c", "start", "winword"], "Darwin": ["open", "-a", "Microsoft Word"]},
    "excel":              {"Windows": ["cmd", "/c", "start", "excel"], "Darwin": ["open", "-a", "Microsoft Excel"]},
    "powerpoint":         {"Windows": ["cmd", "/c", "start", "powerpnt"], "Darwin": ["open", "-a", "Microsoft PowerPoint"]},
    "notion":             {"Windows": ["cmd", "/c", "start", "notion:"], "Darwin": ["open", "-a", "Notion"]},
    "obsidian":           {"Windows": ["cmd", "/c", "start", "obsidian:"], "Darwin": ["open", "-a", "Obsidian"]},
    # ── Dev tools ──
    "postman":            {"Windows": ["cmd", "/c", "start", "postman:"], "Darwin": ["open", "-a", "Postman"]},
    "figma":              {"Windows": ["cmd", "/c", "start", "figma:"], "Darwin": ["open", "-a", "Figma"]},
    "docker":             {"Windows": ["cmd", "/c", "start", "", "Docker Desktop"], "Darwin": ["open", "-a", "Docker"]},
    "docker desktop":     {"Windows": ["cmd", "/c", "start", "", "Docker Desktop"], "Darwin": ["open", "-a", "Docker"]},
    "github desktop":     {"Windows": ["cmd", "/c", "start", "github:"], "Darwin": ["open", "-a", "GitHub Desktop"]},
    "insomnia":           {"Windows": ["cmd", "/c", "start", "", "Insomnia"], "Darwin": ["open", "-a", "Insomnia"]},
    # ── System utilities ──
    "calculator":         {"Windows": ["calc"], "Darwin": ["open", "-a", "Calculator"]},
    "calc":               {"Windows": ["calc"], "Darwin": ["open", "-a", "Calculator"]},
    "file explorer":      {"Windows": ["explorer"], "Darwin": ["open", "."]},
    "explorer":           {"Windows": ["explorer"], "Darwin": ["open", "."]},
    "finder":             {"Windows": ["explorer"], "Darwin": ["open", "."]},
    "paint":              {"Windows": ["mspaint"], "Darwin": ["open", "-a", "Preview"]},
    "task manager":       {"Windows": ["taskmgr"], "Darwin": ["open", "-a", "Activity Monitor"]},
    "activity monitor":   {"Windows": ["taskmgr"], "Darwin": ["open", "-a", "Activity Monitor"]},
    "settings":           {"Windows": ["cmd", "/c", "start", "ms-settings:"], "Darwin": ["open", "-a", "System Preferences"]},
    "control panel":      {"Windows": ["control"], "Darwin": ["open", "-a", "System Preferences"]},
    "snipping tool":      {"Windows": ["snippingtool"], "Darwin": ["open", "-a", "Screenshot"]},
    "snip & sketch":      {"Windows": ["cmd", "/c", "start", "ms-screenclip:"], "Darwin": ["open", "-a", "Screenshot"]},
    # ── Media ──
    "vlc":                {"Windows": ["cmd", "/c", "start", "", "vlc"], "Darwin": ["open", "-a", "VLC"]},
    "obs":                {"Windows": ["cmd", "/c", "start", "", "obs64.exe"], "Darwin": ["open", "-a", "OBS"]},
    "obs studio":         {"Windows": ["cmd", "/c", "start", "", "obs64.exe"], "Darwin": ["open", "-a", "OBS"]},
    # ── AI tools ──
    "antigravity":        {"Windows": ["agy"], "Darwin": ["agy"]},
    "agy":                {"Windows": ["agy"], "Darwin": ["agy"]},
}


def _fuzzy_match_app(query: str, threshold: float = 0.6) -> str | None:
    """Find the closest matching app alias using fuzzy string matching."""
    matches = difflib.get_close_matches(query, _APP_ALIASES.keys(), n=1, cutoff=threshold)
    return matches[0] if matches else None


async def _handle_open_application(session: AsyncSession, user_id: UUID, app_name: str) -> dict:
    """Launch an application on the host machine."""
    app_key = app_name.strip().lower()
    current_os = platform.system()  # 'Windows' or 'Darwin'

    # 1. Exact match in alias map
    resolved_key = app_key if app_key in _APP_ALIASES else _fuzzy_match_app(app_key)

    if resolved_key:
        os_commands = _APP_ALIASES[resolved_key]
        cmd = os_commands.get(current_os)
        if not cmd:
            return {"error": f"'{app_name}' is not supported on {current_os}."}
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=(current_os == "Windows"),
            )
            _log.info(f"APP_LAUNCH | Launched '{resolved_key}' (requested: '{app_name}') via alias map")

            # Log to ActionLog for audit trail
            log_entry = ActionLog(
                user_id=user_id,
                action_type="open_application",
                payload={"app_name": app_name, "resolved": resolved_key, "command": cmd},
                result="success",
                confirmed_by_user=False,
            )
            session.add(log_entry)
            await session.flush()

            result = {"status": "launched", "app": app_name}
            if resolved_key != app_key:
                result["matched_as"] = resolved_key
            return result

        except FileNotFoundError:
            _log.warning(f"APP_LAUNCH | Executable not found for '{resolved_key}'")
            log_entry = ActionLog(
                user_id=user_id,
                action_type="open_application",
                payload={"app_name": app_name, "resolved": resolved_key},
                result="failed",
                confirmed_by_user=False,
            )
            session.add(log_entry)
            await session.flush()
            return {"error": f"Could not find the executable for '{app_name}'. It may not be installed or not in PATH."}
        except OSError as e:
            _log.error(f"APP_LAUNCH | OS error launching '{resolved_key}': {e}")
            return {"error": f"Failed to launch '{app_name}': {str(e)}"}

    # 2. Fallback: try os.startfile on Windows or 'open -a' on macOS
    _log.info(f"APP_LAUNCH | No alias match for '{app_name}', trying OS fallback")
    try:
        if current_os == "Windows":
            os.startfile(app_key)
        elif current_os == "Darwin":
            subprocess.Popen(
                ["open", "-a", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            return {"error": f"Unsupported operating system: {current_os}"}

        log_entry = ActionLog(
            user_id=user_id,
            action_type="open_application",
            payload={"app_name": app_name, "method": "os_fallback"},
            result="success",
            confirmed_by_user=False,
        )
        session.add(log_entry)
        await session.flush()

        return {"status": "launched", "app": app_name}
    except Exception as e:
        # Suggest close matches if the app wasn't found at all
        suggestions = difflib.get_close_matches(app_key, _APP_ALIASES.keys(), n=3, cutoff=0.4)
        err = {"error": f"Could not open '{app_name}'. It may not be installed."}
        if suggestions:
            err["did_you_mean"] = suggestions
        return err


# ─────────────────────────────────────────────────────────────────────────────
# Repo Analyzer
# ─────────────────────────────────────────────────────────────────────────────

_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".next", ".nuxt", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    "target", ".gradle", ".idea", ".vs", ".vscode", "vendor", "Pods",
    "coverage", ".turbo", ".cache", "out", "bin", "obj", ".dart_tool",
    ".pub-cache", "_build", "deps", "elm-stuff",
}

_KEY_CONFIG_FILES = {
    # Package managers & build systems
    "package.json", "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Cargo.toml", "go.mod", "go.sum", "pom.xml", "build.gradle", "build.gradle.kts",
    "Gemfile", "composer.json", "mix.exs", "pubspec.yaml", "Package.swift",
    # Containerization & infra
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    ".env.example", "Makefile", "CMakeLists.txt", "Procfile",
    # JS/TS config
    "tsconfig.json", "next.config.js", "next.config.mjs", "next.config.ts",
    "vite.config.ts", "vite.config.js", "webpack.config.js",
    "tailwind.config.js", "tailwind.config.ts",
    # Database & ORM
    "alembic.ini", "prisma/schema.prisma",
    # CI/CD
    ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
    "azure-pipelines.yml", ".circleci/config.yml",
}

_CI_CD_PATHS = [
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    ".circleci/config.yml",
    ".travis.yml",
    "bitbucket-pipelines.yml",
    "vercel.json",
    "netlify.toml",
    "fly.toml",
    "railway.json",
    "render.yaml",
]

_README_FILES = {"README.md", "README.txt", "README.rst", "README", "readme.md"}

_MAX_FILE_READ_BYTES = 8_000
_MAX_TREE_DEPTH = 5
_MAX_TREE_ENTRIES = 500

# Extensions that count as "code" for LOC counting
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".m",
    ".scala", ".ex", ".exs", ".erl", ".hs", ".lua", ".r", ".dart",
    ".vue", ".svelte", ".html", ".css", ".scss", ".less", ".sass",
    ".sql", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
    ".yml", ".yaml", ".toml", ".json", ".xml", ".graphql",
}


def _walk_repo(
    root: Path, max_depth: int = _MAX_TREE_DEPTH
) -> tuple[list[str], dict[str, int], list[Path], list[Path], int]:
    """
    Walk the repo directory and return:
    - tree_lines: indented file tree strings (box-drawing formatted)
    - ext_counts: {extension: count}
    - config_files: list of Paths to key config files found
    - readme_files: list of Paths to README files found
    - total_loc: approximate total lines of code across all code files
    """
    tree_lines: list[str] = []
    ext_counts: dict[str, int] = {}
    config_files: list[Path] = []
    readme_files: list[Path] = []
    total_loc = 0
    entry_count = 0

    def _recurse(directory: Path, depth: int, prefix: str):
        nonlocal entry_count, total_loc
        if depth > max_depth or entry_count > _MAX_TREE_ENTRIES:
            return

        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        # Filter out ignored/hidden dirs
        visible = [
            e for e in entries
            if not (e.is_dir() and (e.name in _IGNORE_DIRS or e.name.startswith(".")))
        ]

        for idx, entry in enumerate(visible):
            entry_count += 1
            if entry_count > _MAX_TREE_ENTRIES:
                tree_lines.append(f"{prefix}... (truncated, too many entries)")
                return

            is_last = idx == len(visible) - 1
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            if entry.is_dir():
                tree_lines.append(f"{prefix}{connector}{entry.name}/")
                _recurse(entry, depth + 1, prefix + extension)
            else:
                tree_lines.append(f"{prefix}{connector}{entry.name}")
                ext = entry.suffix.lower() if entry.suffix else "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

                if entry.name in _KEY_CONFIG_FILES:
                    config_files.append(entry)
                if entry.name in _README_FILES:
                    readme_files.append(entry)

                # Count lines of code
                if ext in _CODE_EXTENSIONS:
                    try:
                        total_loc += sum(1 for _ in open(entry, "rb"))
                    except (PermissionError, OSError):
                        pass

    _recurse(root, 0, "")
    return tree_lines, ext_counts, config_files, readme_files, total_loc


def _safe_read(path: Path, max_bytes: int = _MAX_FILE_READ_BYTES) -> str:
    """Read a file safely, returning its content truncated to max_bytes."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_bytes:
            return content[:max_bytes] + "\n... (truncated)"
        return content
    except Exception:
        return "(could not read file)"


def _get_git_info(repo_path: Path) -> dict[str, str] | None:
    """Extract git metadata from the repo if it's a git repository."""
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return None

    info: dict[str, str] = {}
    try:
        # Current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=5,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()

        # Last commit
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%ar)"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=5,
        )
        if result.returncode == 0:
            info["last_commit"] = result.stdout.strip()

        # Total commit count
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=5,
        )
        if result.returncode == 0:
            info["total_commits"] = result.stdout.strip()

        # Remote URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=str(repo_path), timeout=5,
        )
        if result.returncode == 0:
            info["remote_url"] = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return info if info else None


def _detect_ci_cd(repo_path: Path) -> list[str]:
    """Detect CI/CD configurations present in the repo."""
    found = []
    for ci_path in _CI_CD_PATHS:
        full_path = repo_path / ci_path
        if full_path.exists():
            if full_path.is_dir():
                # e.g. .github/workflows — list the workflow files
                try:
                    workflow_files = [f.name for f in full_path.iterdir() if f.is_file()]
                    found.append(f"{ci_path}/ ({', '.join(workflow_files[:5])})")
                except PermissionError:
                    found.append(f"{ci_path}/")
            else:
                found.append(ci_path)
    return found


async def _handle_analyze_repository(session: AsyncSession, user_id: UUID, path: str) -> dict:
    """Analyze a code repository and return a structured overview."""
    repo_path = Path(path)

    if not repo_path.exists():
        return {"error": f"Path does not exist: {path}"}
    if not repo_path.is_dir():
        return {"error": f"Path is not a directory: {path}"}

    _log.info(f"REPO_ANALYZE | Starting analysis of {repo_path.name} at {path}")

    # Walk the repo
    tree_lines, ext_counts, config_files, readme_files, total_loc = _walk_repo(repo_path)

    # Git metadata
    git_info = _get_git_info(repo_path)

    # CI/CD detection
    ci_cd = _detect_ci_cd(repo_path)

    # Collect key file contents
    file_contents: dict[str, str] = {}
    for cf in config_files:
        rel = str(cf.relative_to(repo_path))
        file_contents[rel] = _safe_read(cf)
    for rf in readme_files:
        rel = str(rf.relative_to(repo_path))
        file_contents[rel] = _safe_read(rf, max_bytes=12_000)

    # Build the analysis context
    tree_str = "\n".join(tree_lines[:300])
    if len(tree_lines) > 300:
        tree_str += "\n... (tree truncated)"

    total_files = sum(ext_counts.values())
    ext_summary = "\n".join(
        f"  {ext}: {count} files"
        for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])[:20]
    )

    config_contents = ""
    for fname, content in file_contents.items():
        config_contents += f"\n--- {fname} ---\n{content}\n"

    git_section = ""
    if git_info:
        git_section = "\n## Git Info\n"
        if "branch" in git_info:
            git_section += f"  Current branch: {git_info['branch']}\n"
        if "last_commit" in git_info:
            git_section += f"  Last commit: {git_info['last_commit']}\n"
        if "total_commits" in git_info:
            git_section += f"  Total commits: {git_info['total_commits']}\n"
        if "remote_url" in git_info:
            git_section += f"  Remote: {git_info['remote_url']}\n"

    ci_section = ""
    if ci_cd:
        ci_section = "\n## CI/CD Configurations\n  " + "\n  ".join(ci_cd) + "\n"

    analysis_prompt = f"""You are a senior software engineer. Analyze this code repository and provide a clear, structured overview.

Repository: {repo_path.name}
Path: {path}
Total files: {total_files}
Approximate lines of code: {total_loc:,}
{git_section}
{ci_section}
## File Tree
{tree_str}

## File Type Distribution
{ext_summary}

## Key Config & Documentation Files
{config_contents if config_contents else "(none found)"}

Provide your analysis in this exact format:

**Tech Stack**: List the languages, frameworks, and key libraries with versions where visible.
**Architecture**: Describe the high-level architecture (monorepo, client-server, microservices, etc.) and how the components relate. Mention any notable infrastructure (Docker, CI/CD, etc.).
**Entry Points**: Where does the code start? Main files, scripts, or commands to run the project.
**Key Dependencies**: List the most important external dependencies and what they're used for.
**Directory Guide**: Brief explanation of what each top-level directory contains and its role in the system.
**Getting Started**: Concrete steps someone new would take to set up, run, and start understanding this codebase.
**Notable Patterns**: Any interesting design patterns, conventions, architecture decisions, or things that stand out.
**Potential Concerns**: Any red flags, missing pieces, or areas that might need attention (optional, only if relevant).

Be concise but thorough. Write as if briefing a developer who needs to contribute to this repo tomorrow."""

    try:
        client = get_client()
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[analysis_prompt],
        )
        analysis = resp.text.strip() if resp.text else "Analysis could not be generated."
    except Exception as e:
        _log.error(f"REPO_ANALYZE | Gemini analysis failed: {e}")
        analysis = f"AI analysis failed: {str(e)}"

    # Log to ActionLog
    log_entry = ActionLog(
        user_id=user_id,
        action_type="analyze_repository",
        payload={"path": path, "repo_name": repo_path.name, "total_files": total_files, "total_loc": total_loc},
        result="success",
        confirmed_by_user=False,
    )
    session.add(log_entry)
    await session.flush()

    _log.info(f"REPO_ANALYZE | Completed analysis of {repo_path.name}: {total_files} files, ~{total_loc:,} LOC")

    response = {
        "repository": repo_path.name,
        "path": str(repo_path),
        "total_files": total_files,
        "total_lines_of_code": total_loc,
        "file_types": dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:15]),
        "config_files_found": [str(cf.relative_to(repo_path)) for cf in config_files],
        "analysis": analysis,
    }

    if git_info:
        response["git"] = git_info
    if ci_cd:
        response["ci_cd"] = ci_cd

    return response
