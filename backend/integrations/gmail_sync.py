import logging
from datetime import datetime, timezone
import json
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from db.session import async_session_factory
from db.models import Integration, EmailMessage, User
from core.crypto import encrypt, decrypt
from agents.gemini_client import get_client
from core.config import settings
from core.state import get_pause_state
from integrations.base import get_adapter

logger = logging.getLogger(__name__)

async def _classify_email(snippet: str) -> dict:
    """Uses Gemini to classify an email's snippet for reply needs and deadlines."""
    try:
        client = get_client()
        prompt = (
            "Analyze the following email snippet.\n"
            "Respond ONLY with a JSON object containing two keys: "
            "'needs_reply' (boolean) and 'deadline_detected' (string, ISO 8601 format, or null if no deadline is present).\n"
            f"Snippet: {snippet}"
        )
        resp = client.models.generate_content(model=settings.GEMINI_MODEL, contents=[prompt])
        raw_json = resp.text.strip()
        # Remove markdown codeblocks if Gemini adds them
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:-3]
        elif raw_json.startswith("```"):
            raw_json = raw_json[3:-3]
        
        parsed = json.loads(raw_json.strip())
        deadline_str = parsed.get("deadline_detected")
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        return {
            "needs_reply": bool(parsed.get("needs_reply", False)),
            "deadline": deadline
        }
    except Exception as e:
        logger.warning(f"Failed to classify email snippet: {e}")
        return {"needs_reply": False, "deadline": None}

async def _sync_user_gmail(session: AsyncSession, integration: Integration):
    adapter = get_adapter("gmail")
    
    # 1. Ensure token is valid
    if not adapter.is_token_valid(integration):
        try:
            new_tokens = await adapter.refresh_access_token(integration)
            integration.access_token_encrypted = encrypt(new_tokens["access_token"])
            if new_tokens.get("refresh_token"):
                integration.refresh_token_encrypted = encrypt(new_tokens["refresh_token"])
            integration.token_expires_at = new_tokens["expires_at"]
            await session.commit()
            await session.refresh(integration)
        except Exception as e:
            logger.error(f"Failed to refresh token for user {integration.user_id}: {e}")
            return
            
    # 2. Build Gmail API client
    access_token = decrypt(integration.access_token_encrypted)
    creds = Credentials(token=access_token)
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    
    # 3. Fetch messages
    try:
        # We fetch a modest batch of recent unread messages
        results = service.users().messages().list(userId='me', q="is:unread", maxResults=20).execute()
        messages = results.get('messages', [])
        
        for msg_ref in messages:
            msg_id = msg_ref['id']
            
            existing = await session.execute(
                select(EmailMessage).where(EmailMessage.gmail_message_id == msg_id)
            )
            if existing.scalar_one_or_none():
                continue
                
            msg_data = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'Subject']).execute()
            
            headers = msg_data.get("payload", {}).get("headers", [])
            from_address = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
            snippet = msg_data.get("snippet", "")
            internal_date = int(msg_data.get("internalDate", 0)) / 1000.0
            received_at = datetime.fromtimestamp(internal_date, tz=timezone.utc)
            
            classification = await _classify_email(snippet)
            
            new_msg = EmailMessage(
                user_id=integration.user_id,
                gmail_message_id=msg_id,
                thread_id=msg_data.get("threadId", ""),
                from_address=from_address,
                subject=subject,
                snippet=snippet,
                received_at=received_at,
                is_read=False,
                needs_reply=classification["needs_reply"],
                deadline_detected=classification["deadline"]
            )
            session.add(new_msg)
        
        integration.last_synced_at = datetime.now(timezone.utc)
        await session.commit()
    except Exception as e:
        logger.error(f"Error syncing Gmail for user {integration.user_id}: {e}")

async def gmail_sync_check():
    """Polls Gmail for new emails across all active integrations."""
    if get_pause_state():
        logger.info("Gmail sync: system paused, skipping cycle.")
        return

    logger.info("Gmail sync: starting check cycle.")
    async with async_session_factory() as session:
        result = await session.execute(
            select(Integration).where(
                and_(
                    Integration.provider == "gmail",
                    Integration.status == "connected"
                )
            )
        )
        integrations = result.scalars().all()
        
        for integration in integrations:
            try:
                await _sync_user_gmail(session, integration)
            except Exception as e:
                logger.error(f"Gmail sync error for integration {integration.id}: {e}", exc_info=True)
                
    logger.info("Gmail sync: cycle complete.")

def start_gmail_sync_engine(scheduler):
    scheduler.add_job(
        gmail_sync_check,
        "interval",
        seconds=settings.PROACTIVE_CHECK_INTERVAL_SECONDS,
        id="gmail_sync_engine",
        replace_existing=True,
    )
    logger.info(f"Gmail sync engine registered: interval={settings.PROACTIVE_CHECK_INTERVAL_SECONDS}s.")
