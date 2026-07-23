from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from db.models import CalendarEvent
from schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate

async def get_calendar_events(session: AsyncSession, user_id: UUID) -> list[CalendarEvent]:
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_calendar_event(session: AsyncSession, user_id: UUID, event_id: UUID) -> CalendarEvent | None:
    stmt = select(CalendarEvent).where(CalendarEvent.user_id == user_id, CalendarEvent.id == event_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_calendar_event(session: AsyncSession, user_id: UUID, event_in: CalendarEventCreate) -> CalendarEvent:
    event = CalendarEvent(user_id=user_id, **event_in.model_dump())
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
