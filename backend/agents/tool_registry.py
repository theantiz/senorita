from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from google.genai.types import FunctionDeclaration, Type, Tool

from db.models import Task, Reminder, CalendarEvent, MemoryEntry, Contact
from memory.embeddings import embed_text
from memory.retrieval import search_similar_memory
from agents.gemini_client import start_chat, get_client
from db.models import Task, Reminder, CalendarEvent, MemoryEntry, Contact, EmailMessage, SlackMessage, Integration, ActionLog
from integrations.base import get_adapter
from core.crypto import decrypt
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64, json
from email.message import EmailMessage as PyEmailMessage
import httpx

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

SENORITA_TOOLS = [
    create_task,
    create_reminder,
    create_calendar_event,
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
        "read_emails": _handle_read_emails,
        "summarize_email": _handle_summarize_email,
        "draft_email_reply": _handle_draft_email_reply,
        "send_email": _handle_send_email,
        "read_slack_messages": _handle_read_slack_messages,
        "draft_slack_reply": _handle_draft_slack_reply,
        "send_slack_message": _handle_send_slack_message,
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
        service = _get_gmail_service(integration)
        msg_data = service.users().messages().get(userId='me', id=email.gmail_message_id, format='full').execute()
        
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
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
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
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[f"Draft a reply to the email '{email.subject}' from '{email.from_address}'.\nIntent: {intent}\nSnippet: {email.snippet}\n\nReturn ONLY the email body text."]
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
        
        service = _get_gmail_service(integration)
        draft = service.users().drafts().create(userId='me', body=create_message).execute()
        
        return {"draft_id": draft['id'], "content": draft_text}
    except Exception as e:
        return {"error": str(e)}

async def _handle_send_email(session: AsyncSession, user_id: UUID, draft_id: str) -> dict:
    integration = (await session.execute(select(Integration).where(Integration.user_id == user_id, Integration.provider == "gmail"))).scalars().first()
    if not integration or integration.status != "connected":
        return {"error": "Gmail not connected."}
        
    # Check per-capability toggle
    if not integration.permissions.get("send_automatically", False):
        return {"error": "confirmation_required"}
        
    # In Module 13, contact message_mode is checked here. We mock it for now.
    # Check if a contact matches the draft's To address and respects it
    
    try:
        service = _get_gmail_service(integration)
        sent_message = service.users().drafts().send(userId='me', body={'id': draft_id}).execute()
        
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
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
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

    if not integration.permissions.get("send_automatically", False):
        return {
            "error": "confirmation_required",
            "detail": "send_automatically is disabled for Slack. Please confirm before sending.",
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


