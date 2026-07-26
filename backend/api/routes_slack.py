"""
api/routes_slack.py

Slack Events API webhook receiver.

Two-step Slack verification:
  1. URL verification challenge (one-time handshake when you register the endpoint).
  2. Signed-request verification on every subsequent event (X-Slack-Signature header).

Event handling:
  - message.im (direct message sent to the bot user) → needs_reply = True
  - app_mention (@ mention in any channel)           → needs_reply = True
  - message in public/private channel (not a mention)→ needs_reply = False

Only events for users who have a connected Slack integration are processed.
Duplicate events (same ts + channel) are silently dropped via the UNIQUE index
on slack_message_ts.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from db.models import Integration, SlackMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack-webhook"])


# ─────────────────────────────────────────────────────────────────────────────
# Signature verification
# ─────────────────────────────────────────────────────────────────────────────

def _verify_slack_signature(raw_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Validate the X-Slack-Signature header using the shared signing secret.
    Rejects requests older than 5 minutes to prevent replay attacks.
    """
    if not settings.SLACK_SIGNING_SECRET:
        # If not configured, skip verification (dev mode). Log a warning.
        logger.warning("SLACK_SIGNING_SECRET not set — skipping signature verification.")
        return True

    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return False

    # Reject stale requests (> 5 minutes old)
    if abs(time.time() - ts_int) > 300:
        return False

    sig_base = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode(),
        sig_base.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# ─────────────────────────────────────────────────────────────────────────────
# Webhook endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def slack_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_signature: str = Header(default=""),
):
    """
    Receives Slack Events API payloads.

    Handles:
    - url_verification challenge (initial setup)
    - event_callback with message / app_mention events
    """
    raw_body = await request.body()

    # ── Signature check ──────────────────────────────────────────────────────
    if not _verify_slack_signature(raw_body, x_slack_request_timestamp, x_slack_signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    payload = await request.json()

    # ── URL Verification (one-time handshake) ─────────────────────────────────
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # ── Event Callbacks ───────────────────────────────────────────────────────
    if payload.get("type") != "event_callback":
        return {"ok": True}

    event = payload.get("event", {})
    event_type = event.get("type", "")
    team_id = payload.get("team_id", "")

    # Only handle message and app_mention events
    if event_type not in ("message", "app_mention"):
        return {"ok": True}

    # Ignore bot messages and message edits/deletions
    if event.get("subtype") or event.get("bot_id"):
        return {"ok": True}

    # ── Find which user this workspace belongs to ─────────────────────────────
    # We store team_id in Integration.permissions["team_id"] at connect time.
    stmt = select(Integration).where(
        Integration.provider == "slack",
        Integration.status == "connected",
    )
    result = await session.execute(stmt)
    integrations = result.scalars().all()

    matching_integration = None
    for integ in integrations:
        if integ.permissions.get("team_id") == team_id:
            matching_integration = integ
            break

    if not matching_integration:
        logger.debug(f"Slack event received for unknown team_id={team_id}. Ignoring.")
        return {"ok": True}

    user_id = matching_integration.user_id
    bot_user_id = matching_integration.permissions.get("bot_user_id", "")

    # ── Determine needs_reply ─────────────────────────────────────────────────
    channel_type = event.get("channel_type", "")   # "im", "channel", "group"
    text = event.get("text", "")

    is_dm = channel_type == "im"
    is_mention = event_type == "app_mention" or (bot_user_id and f"<@{bot_user_id}>" in text)
    needs_reply = is_dm or is_mention

    # ── Write to slack_messages (upsert-safe via unique index on ts) ──────────
    slack_msg = SlackMessage(
        user_id=user_id,
        slack_channel_id=event.get("channel", ""),
        slack_message_ts=event.get("ts", ""),
        channel_name=event.get("channel_type", ""),   # enriched by sync job later
        from_user=event.get("user", "unknown"),
        body_snippet=text[:512],                       # store first 512 chars
        received_at=datetime.fromtimestamp(
            float(event.get("ts", time.time())), tz=timezone.utc
        ),
        needs_reply=needs_reply,
    )

    try:
        session.add(slack_msg)
        await session.commit()
        logger.info(
            f"Slack message stored: channel={slack_msg.slack_channel_id} "
            f"ts={slack_msg.slack_message_ts} needs_reply={needs_reply}"
        )
    except Exception as exc:
        await session.rollback()
        # Duplicate ts → already stored, silently ignore
        if "unique" in str(exc).lower():
            logger.debug(f"Duplicate Slack event ts={event.get('ts')} ignored.")
        else:
            logger.error(f"Error storing Slack message: {exc}", exc_info=True)

    return {"ok": True}
