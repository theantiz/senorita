"""
api/routes_whatsapp.py

WhatsApp Cloud API webhook endpoints.

Two routes:
  GET  /api/v1/whatsapp/webhook  — Meta hub.challenge verification handshake
  POST /api/v1/whatsapp/webhook  — Receive inbound messages from Meta

Design principles:
  - Webhook POST must ack in < 5 seconds (Meta will retry otherwise).
    We do NO AI work here — we only write an IncomingMessage row to the
    DB queue and return HTTP 200. The processor worker handles AI + reply.

  - Multi-tenant: the incoming `phone_number_id` from Meta metadata is used
    to look up which Integration (and therefore which User) owns that number.
    Integration.permissions["phone_number_id"] is the key.

  - HMAC-SHA256 signature verification is enforced on every POST using the
    app's WHATSAPP_WEBHOOK_VERIFY_TOKEN as the signing secret.

  - Sender whitelist (WHATSAPP_ALLOWED_NUMBERS) is applied after signature
    verification and before writing to the queue.
"""

import json
import logging
from fastapi import APIRouter, Request, Response, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session_factory
from db.models import Integration, IncomingMessage
from integrations.whatsapp import verify_webhook_signature
from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_allowed_numbers() -> set[str]:
    """Returns the set of whitelisted E.164 numbers, or empty set (= allow all)."""
    raw = settings.WHATSAPP_ALLOWED_NUMBERS.strip()
    if not raw:
        return set()
    return {n.strip() for n in raw.split(",") if n.strip()}


async def _resolve_user_from_phone_number_id(
    session: AsyncSession, phone_number_id: str
):
    """
    Look up the User who owns the given Meta phone_number_id.

    The Integration row for provider='whatsapp' stores the phone_number_id
    in its `permissions` JSONB column under the key 'phone_number_id'.

    Returns the User instance or None if not found.
    """
    from db.models import User

    stmt = (
        select(Integration)
        .where(
            Integration.provider == "whatsapp",
            Integration.status == "connected",
            # Cast JSONB → text for equality comparison
            Integration.permissions["phone_number_id"].astext == phone_number_id,
        )
    )
    result = await session.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        return None

    user_result = await session.execute(
        select(User).where(User.id == integration.user_id)
    )
    return user_result.scalars().first()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/whatsapp/webhook  — Meta verification handshake
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/webhook")
async def whatsapp_webhook_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """
    Meta calls this endpoint when you first register the webhook URL in the
    Meta Developer Console. It sends a GET with three query parameters.
    We must respond with the hub.challenge value if the verify token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully.")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(
        f"WhatsApp webhook verification failed. "
        f"mode={hub_mode!r} token={hub_verify_token!r}"
    )
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/whatsapp/webhook  — Receive inbound messages
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook", status_code=200)
async def whatsapp_webhook_receive(request: Request):
    """
    Meta POSTs incoming message events here.

    Fast path (target < 20ms):
      1. Read raw body (needed for HMAC verification)
      2. Verify X-Hub-Signature-256
      3. Parse JSON — extract phone_number_id, sender phone, message text
      4. Resolve User via phone_number_id → Integration lookup
      5. Apply sender whitelist (if configured)
      6. Write IncomingMessage(status='pending') to DB queue
      7. Return {"ok": true}

    The processor worker does the AI call and sends the reply asynchronously.
    """
    # Step 1 — read raw body for HMAC verification
    raw_body = await request.body()

    # Step 2 — verify HMAC signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_webhook_signature(raw_body, signature, settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN):
        logger.warning("WhatsApp webhook: invalid HMAC signature — request rejected.")
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    # Step 3 — parse body
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("WhatsApp webhook: body is not valid JSON.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # Safely navigate the Meta webhook payload structure
    # Structure: {object, entry: [{changes: [{value: {metadata, messages}}]}]}
    try:
        entries = body.get("entry", [])
        if not entries:
            # Meta sends test pings with no entry — ack silently
            return {"ok": True}

        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                if not messages:
                    continue  # status updates (read receipts, etc.) — ignore

                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")

                for message in messages:
                    # Only handle inbound text messages for now
                    if message.get("type") != "text":
                        logger.info(
                            f"WhatsApp webhook: skipping non-text message type={message.get('type')}"
                        )
                        continue

                    sender_phone = message.get("from", "")
                    text_body = message.get("text", {}).get("body", "").strip()

                    if not sender_phone or not text_body:
                        continue

                    # Step 4 — resolve User via phone_number_id
                    async with async_session_factory() as session:
                        user = await _resolve_user_from_phone_number_id(
                            session, phone_number_id
                        )

                        if not user:
                            logger.warning(
                                f"WhatsApp webhook: no connected integration found "
                                f"for phone_number_id={phone_number_id!r}. "
                                "Message dropped. Set up this number in the integrations UI."
                            )
                            continue

                        # Step 5 — sender whitelist check
                        allowed = _get_allowed_numbers()
                        if allowed and sender_phone not in allowed:
                            logger.info(
                                f"WhatsApp webhook: {sender_phone} not in allowlist — dropped."
                            )
                            continue

                        # Step 6 — enqueue message
                        incoming = IncomingMessage(
                            user_id=user.id,
                            channel="whatsapp",
                            sender_id=sender_phone,
                            content=text_body,
                            status="pending",
                        )
                        session.add(incoming)
                        await session.commit()
                        logger.info(
                            f"WhatsApp message queued: id={incoming.id} "
                            f"from={sender_phone} user={user.id}"
                        )

    except Exception as e:
        # Log but always return 200 — Meta retries on non-200, causing duplicate processing
        logger.error(f"WhatsApp webhook processing error: {e}", exc_info=True)

    # Step 7 — always ack
    return {"ok": True}
