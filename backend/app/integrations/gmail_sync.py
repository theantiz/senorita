import json
import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client
from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.state import get_pause_state
from app.db.models import Contact, EmailMessage, Integration, User
from app.db.session import async_session_factory
from app.integrations.base import get_adapter

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
        resp = await client.aio.models.generate_content(model=settings.GEMINI_MODEL, contents=[prompt])
        raw_json = (resp.text or '').strip()
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
        import asyncio
        results = await asyncio.to_thread(lambda: service.users().messages().list(userId='me', q="is:unread", maxResults=20).execute())
        messages = results.get('messages', [])

        for msg_ref in messages:
            msg_id = msg_ref['id']

            existing = await session.execute(
                select(EmailMessage).where(EmailMessage.gmail_message_id == msg_id)
            )
            if existing.scalar_one_or_none():
                continue

            msg_data = await asyncio.to_thread(lambda id=msg_id: service.users().messages().get(userId='me', id=id, format='metadata', metadataHeaders=['From', 'Subject']).execute())

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
                direction='inbound',
                received_at=received_at,
                is_read=False,
                needs_reply=classification["needs_reply"],
                deadline_detected=classification["deadline"]
            )
            session.add(new_msg)

        await session.commit()
    except Exception as e:
        logger.error(f"Error syncing inbound Gmail for user {integration.user_id}: {e}")

    # now sync sent folder on the same pass
    await _sync_user_gmail_sent(session, integration, service)

    integration.last_synced_at = datetime.now(timezone.utc)
    await session.commit()


async def _sync_user_gmail_sent(session: AsyncSession, integration: Integration, service):
    """Polls the Sent folder for outbound emails. Skips classification entirely."""
    try:
        import asyncio
        results = await asyncio.to_thread(lambda: service.users().messages().list(userId='me', q="in:sent", maxResults=20).execute())
        messages = results.get('messages', [])

        for msg_ref in messages:
            msg_id = msg_ref['id']

            # dedup — same pattern as inbound
            existing = await session.execute(
                select(EmailMessage).where(EmailMessage.gmail_message_id == msg_id)
            )
            if existing.scalar_one_or_none():
                continue

            msg_data = await asyncio.to_thread(lambda id=msg_id: service.users().messages().get(
                userId='me', id=id, format='metadata',
                metadataHeaders=['From', 'To', 'Subject']
            ).execute())

            headers = msg_data.get("payload", {}).get("headers", [])
            from_address = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown")
            to_address = next((h["value"] for h in headers if h["name"].lower() == "to"), None)
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
            snippet = msg_data.get("snippet", "")
            internal_date = int(msg_data.get("internalDate", 0)) / 1000.0
            sent_at = datetime.fromtimestamp(internal_date, tz=timezone.utc)

            new_msg = EmailMessage(
                user_id=integration.user_id,
                gmail_message_id=msg_id,
                thread_id=msg_data.get("threadId", ""),
                from_address=from_address,
                to_address=to_address,
                subject=subject,
                snippet=snippet,
                direction='outbound',
                received_at=sent_at,
                is_read=True,
                needs_reply=None,
                deadline_detected=None
            )
            session.add(new_msg)

        await session.commit()
        logger.info(f"Sent-folder sync complete for user {integration.user_id}")
    except Exception as e:
        logger.error(f"Error syncing sent Gmail for user {integration.user_id}: {e}")

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
        seconds=600, # 10 minutes for email
        id="gmail_sync_engine",
        replace_existing=True,
    )
    logger.info(f"Gmail sync engine registered: interval={settings.PROACTIVE_CHECK_INTERVAL_SECONDS}s.")
