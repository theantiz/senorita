from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CalendarEvent
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate


async def get_calendar_events(session: AsyncSession, user_id: UUID) -> list[CalendarEvent]:
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id).order_by(CalendarEvent.start_at)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def find_calendar_conflicts(
    session: AsyncSession,
    user_id: UUID,
    start_at,
    end_at,
    exclude_event_id: UUID | None = None,
) -> list[CalendarEvent]:
    stmt = select(CalendarEvent).where(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_at < end_at,
        CalendarEvent.end_at > start_at,
    )
    if exclude_event_id:
        stmt = stmt.where(CalendarEvent.id != exclude_event_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_calendar_event(session: AsyncSession, user_id: UUID, event_id: UUID) -> CalendarEvent | None:
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id, CalendarEvent.id == event_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_calendar_event(session: AsyncSession, user_id: UUID, event_in: CalendarEventCreate) -> CalendarEvent:
    payload = event_in.model_dump()
    payload["source"] = "manual"
    payload.setdefault("source_calendar", "local")
    payload["google_event_id"] = None

    conflicts = await find_calendar_conflicts(session, user_id, event_in.start_at, event_in.end_at)
    payload["conflict_flags"] = [
        {
            "id": str(event.id),
            "title": event.title,
            "source": event.source,
            "start_at": event.start_at.isoformat(),
            "end_at": event.end_at.isoformat(),
        }
        for event in conflicts
    ]

    event = CalendarEvent(user_id=user_id, **payload)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event

async def update_calendar_event(session: AsyncSession, user_id: UUID, event_id: UUID, event_in: CalendarEventUpdate) -> CalendarEvent | None:
    event = await get_calendar_event(session, user_id, event_id)
    if not event:
        return None
    for k, v in event_in.model_dump(exclude_unset=True).items():
        setattr(event, k, v)
    await session.commit()
    await session.refresh(event)
    return event

async def delete_calendar_event(session: AsyncSession, user_id: UUID, event_id: UUID) -> bool:
    event = await get_calendar_event(session, user_id, event_id)
    if not event:
        return False
    await session.delete(event)
    await session.commit()
    return True
