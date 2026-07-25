"""
workers/messaging/processor.py

Asynchronous message processor — the heart of the messaging platform.

Runs on an APScheduler interval (default: every 5 seconds). Picks up
IncomingMessage rows with status='pending', processes them through the
AI orchestrator via ConversationService, sends the reply via the
appropriate channel sender, and marks rows as 'done' or 'error'.

Key design decisions:
  - SELECT ... FOR UPDATE SKIP LOCKED ensures that even if two scheduler
    ticks somehow overlap, each message is processed exactly once.
  - Rows are first marked 'processing' and committed, so a crash during
    AI generation leaves the row in 'processing' state rather than
    disappearing. A recovery job (future work) can reset these.
  - Channel dispatch is a simple if/elif — add a new branch when a new
    channel is implemented. The ConversationService (AI step) does not
    change.
  - Credentials are always fetched fresh from the DB per message to
    support token rotation without worker restart.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from db.session import async_session_factory
from db.models import User, Integration, IncomingMessage
from services.conversation_service import handle_incoming
from integrations.whatsapp import whatsapp_sender
from core.crypto import decrypt
from core.state import get_pause_state
from core.config import settings

logger = logging.getLogger(__name__)

# Maximum messages to process per scheduler tick.
# Keeps individual ticks bounded even under high load.
BATCH_SIZE = 10


# ─────────────────────────────────────────────────────────────────────────────
# Credential helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_whatsapp_integration(session, user_id) -> Integration | None:
    """Fetch the connected WhatsApp Integration for a given user."""
    result = await session.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == "whatsapp",
            Integration.status == "connected",
        )
    )
    return result.scalars().first()


# ─────────────────────────────────────────────────────────────────────────────
# Channel dispatch
# ─────────────────────────────────────────────────────────────────────────────

async def _dispatch_reply(session, msg: IncomingMessage, reply: str) -> None:
    """
    Route the AI reply back through the correct channel.
    Extend this function when adding new channels (SMS, Slack, etc.).
    """
    if msg.channel == "whatsapp":
        integration = await _get_whatsapp_integration(session, msg.user_id)
        if not integration:
            raise ValueError(
                f"WhatsApp integration not connected for user {msg.user_id}. "
                "Cannot send reply."
            )
        access_token = decrypt(integration.access_token_encrypted)
        phone_number_id = integration.permissions.get("phone_number_id", "")
        if not phone_number_id:
            raise ValueError(
                f"phone_number_id missing in Integration.permissions for user {msg.user_id}."
            )
        await whatsapp_sender.send(
            to_phone=msg.sender_id,
            text=reply,
            access_token=access_token,
            phone_number_id=phone_number_id,
        )
    else:
        raise NotImplementedError(f"Channel '{msg.channel}' dispatch not implemented yet.")


# ─────────────────────────────────────────────────────────────────────────────
# Core processing job
# ─────────────────────────────────────────────────────────────────────────────

async def process_pending_messages() -> None:
    """
    APScheduler job — polls for pending IncomingMessage rows and processes them.

    Flow per message:
      1. Fetch user
      2. Call ConversationService.handle_incoming() → AI reply string
      3. Dispatch reply via channel sender
      4. Mark row status='done'
      On any exception: mark status='error', store error message.
    """
    if get_pause_state():
        return  # Honour the global pause flag

    async with async_session_factory() as session:
        # --- Atomic lock: fetch pending rows and mark as 'processing' ---
        stmt = (
            select(IncomingMessage)
            .where(IncomingMessage.status == "pending")
            .order_by(IncomingMessage.created_at.asc())
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)   # prevents double-processing
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        if not messages:
            return  # Nothing to do this tick

        logger.info(f"Message processor: picked up {len(messages)} pending message(s).")

        # Mark all fetched rows as 'processing' before doing any work
        for msg in messages:
            msg.status = "processing"
        await session.flush()  # write without releasing the row locks

        # --- Process each message ---
        for msg in messages:
            try:
                user_result = await session.execute(
                    select(User).where(User.id == msg.user_id)
                )
                user = user_result.scalars().first()
                if not user:
                    raise ValueError(f"User {msg.user_id} not found.")

                # AI orchestration (full Señorita context)
                reply = await handle_incoming(session, user, msg)

                # Send reply via the originating channel
                await _dispatch_reply(session, msg, reply)

                msg.status = "done"
                msg.processed_at = datetime.now(timezone.utc)
                logger.info(
                    f"Message {msg.id} ({msg.channel}/{msg.sender_id}): done."
                )

            except Exception as exc:
                msg.status = "error"
                msg.error = str(exc)
                msg.processed_at = datetime.now(timezone.utc)
                logger.error(
                    f"Message {msg.id} ({msg.channel}/{msg.sender_id}) failed: {exc}",
                    exc_info=True,
                )

        await session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler registration
# ─────────────────────────────────────────────────────────────────────────────

def start_message_processor(scheduler) -> None:
    """
    Register the processor job with the shared APScheduler instance.
    Called from main.py lifespan alongside the other workers.
    """
    scheduler.add_job(
        process_pending_messages,
        "interval",
        seconds=settings.WHATSAPP_MESSAGE_POLL_INTERVAL_SECONDS,
        id="message_processor",
        replace_existing=True,
    )
    logger.info(
        f"Message processor registered: "
        f"interval={settings.WHATSAPP_MESSAGE_POLL_INTERVAL_SECONDS}s, "
        f"batch_size={BATCH_SIZE}."
    )
