import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.state import get_pause_state
from app.db.models import CalendarEvent, Integration
from app.db.session import async_session_factory
from app.integrations.base import get_adapter
from app.integrations.gmail import has_calendar_scopes

logger = logging.getLogger(__name__)

SYNC_TOKEN_KEY = "google_calendar_sync_token"


def _parse_google_datetime(value: dict) -> datetime:
    if value.get("dateTime"):
        return datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))

    if value.get("date"):
        parsed = datetime.fromisoformat(value["date"])
        return parsed.replace(tzinfo=timezone.utc)

    raise ValueError("Google Calendar event is missing start/end time data.")


def _extract_attendees(event: dict) -> list[dict]:
    attendees = []
    for attendee in event.get("attendees", []) or []:
        attendees.append(
            {
                "email": attendee.get("email"),
                "display_name": attendee.get("displayName"),
                "response_status": attendee.get("responseStatus"),
            }
        )
    return attendees


async def _ensure_google_token(session: AsyncSession, integration: Integration) -> bool:
    adapter = get_adapter("gmail")
    if adapter.is_token_valid(integration):
        return True

    try:
        new_tokens = await adapter.refresh_access_token(integration)
        integration.access_token_encrypted = encrypt(new_tokens["access_token"])
        if new_tokens.get("refresh_token"):
            integration.refresh_token_encrypted = encrypt(new_tokens["refresh_token"])
        integration.token_expires_at = new_tokens["expires_at"]
        await session.commit()
        await session.refresh(integration)
        return True
    except Exception as exc:
        logger.error(f"Failed to refresh Google token for Calendar sync user {integration.user_id}: {exc}")
        integration.status = "token_expired"
        await session.commit()
        return False


async def _upsert_google_event(session: AsyncSession, integration: Integration, event: dict) -> None:
    google_event_id = event.get("id")
    if not google_event_id:
        return

    existing_res = await session.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == integration.user_id,
            CalendarEvent.google_event_id == google_event_id,
        )
    )
    existing = existing_res.scalars().first()

    if event.get("status") == "cancelled":
        if existing:
            await session.delete(existing)
        return

    try:
        start_at = _parse_google_datetime(event.get("start", {}))
        end_at = _parse_google_datetime(event.get("end", {}))
    except ValueError as exc:
        logger.warning(f"Skipping Google Calendar event {google_event_id}: {exc}")
        return

    title = event.get("summary") or "(No title)"
    attendees = _extract_attendees(event)

    if existing:
        existing.title = title
        existing.start_at = start_at
        existing.end_at = end_at
        existing.attendees = attendees
        existing.source = "google_calendar"
        existing.source_calendar = "primary"
    else:
        session.add(
            CalendarEvent(
                user_id=integration.user_id,
                title=title,
                start_at=start_at,
                end_at=end_at,
                attendees=attendees,
                source="google_calendar",
                source_calendar="primary",
                google_event_id=google_event_id,
            )
        )


async def _sync_user_google_calendar(session: AsyncSession, integration: Integration) -> None:
    permissions = dict(integration.permissions or {})
    if not permissions.get("calendar_read", True):
        logger.debug(f"Google Calendar sync disabled by permission for user {integration.user_id}.")
        return

    if not has_calendar_scopes(integration.scopes):
        logger.info(f"Google Calendar scopes missing for user {integration.user_id}; reconnect required.")
        return

    if not await _ensure_google_token(session, integration):
        return

    access_token = decrypt(integration.access_token_encrypted)
    service = build("calendar", "v3", credentials=Credentials(token=access_token), cache_discovery=False)

    sync_token = permissions.get(SYNC_TOKEN_KEY)
    page_token = None

    while True:
        params = {
            "calendarId": "primary",
            "maxResults": 2500,
            "showDeleted": True,
            "singleEvents": True,
        }
        if sync_token:
            params["syncToken"] = sync_token
        if page_token:
            params["pageToken"] = page_token

        try:
            import asyncio
            response = await asyncio.to_thread(lambda: service.events().list(**params).execute())
        except HttpError as exc:
            if getattr(exc.resp, "status", None) == 410:
                logger.info(f"Google Calendar sync token expired for user {integration.user_id}; resetting cursor.")
                permissions.pop(SYNC_TOKEN_KEY, None)
                integration.permissions = permissions
                await session.commit()
                return
            raise

        for event in response.get("items", []):
            await _upsert_google_event(session, integration, event)

        page_token = response.get("nextPageToken")
        if page_token:
            continue

        next_sync_token = response.get("nextSyncToken")
        if next_sync_token:
            permissions[SYNC_TOKEN_KEY] = next_sync_token
            integration.permissions = permissions
        break

    integration.last_synced_at = datetime.now(timezone.utc)
    await session.commit()


async def google_calendar_sync_check():
    """One-way Google Calendar -> Senorita sync across connected Google integrations."""
    if get_pause_state():
        logger.info("Google Calendar sync: system paused, skipping cycle.")
        return

    logger.info("Google Calendar sync: starting check cycle.")
    async with async_session_factory() as session:
        result = await session.execute(
            select(Integration).where(
                and_(
                    Integration.provider == "gmail",
                    Integration.status == "connected",
                )
            )
        )
        integrations = result.scalars().all()

        for integration in integrations:
            try:
                await _sync_user_google_calendar(session, integration)
            except Exception as exc:
                logger.error(
                    f"Google Calendar sync error for integration {integration.id}: {exc}",
                    exc_info=True,
                )

    logger.info("Google Calendar sync: cycle complete.")


def start_google_calendar_sync_engine(scheduler):
    scheduler.add_job(
        google_calendar_sync_check,
        "interval",
        seconds=settings.PROACTIVE_CHECK_INTERVAL_SECONDS,
        id="google_calendar_sync_engine",
        replace_existing=True,
    )
    logger.info(
        f"Google Calendar sync engine registered: interval={settings.PROACTIVE_CHECK_INTERVAL_SECONDS}s."
    )
