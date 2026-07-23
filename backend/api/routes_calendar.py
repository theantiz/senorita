from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from db.session import get_db
from db.models import User
from schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate, CalendarEventRead
from services.calendar_service import get_calendar_events, get_calendar_event, create_calendar_event, update_calendar_event, delete_calendar_event
from core.security import get_current_user

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
