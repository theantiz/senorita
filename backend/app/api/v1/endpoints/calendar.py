from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.api.deps import get_db
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventRead, CalendarEventUpdate
from app.services.calendar_service import (
    create_calendar_event,
    delete_calendar_event,
    get_calendar_event,
    get_calendar_events,
    update_calendar_event,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.get("", response_model=list[CalendarEventRead])
async def list_calendar_events(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_calendar_events(session, current_user.id)

@router.get("/{event_id}", response_model=CalendarEventRead)
async def read_calendar_event(event_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    event = await get_calendar_event(session, current_user.id, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Calendar Event not found")
    return event

@router.post("", response_model=CalendarEventRead)
async def create_new_calendar_event(event_in: CalendarEventCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_calendar_event(session, current_user.id, event_in)

@router.patch("/{event_id}", response_model=CalendarEventRead)
async def update_existing_calendar_event(event_id: UUID, event_in: CalendarEventUpdate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    event = await update_calendar_event(session, current_user.id, event_id, event_in)
    if not event:
        raise HTTPException(status_code=404, detail="Calendar Event not found")
    return event

@router.delete("/{event_id}")
async def delete_existing_calendar_event(event_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_calendar_event(session, current_user.id, event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Calendar Event not found")
    return {"ok": True}
