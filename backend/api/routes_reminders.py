from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from db.session import get_db
from db.models import User
from schemas.reminder import ReminderCreate, ReminderUpdate, ReminderRead
from services.reminder_service import get_reminders, get_reminder, create_reminder, update_reminder, delete_reminder
from core.security import get_current_user

router = APIRouter(prefix="/reminders", tags=["reminders"])

@router.get("", response_model=list[ReminderRead])
async def list_reminders(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_reminders(session, current_user.id)

@router.get("/{reminder_id}", response_model=ReminderRead)
async def read_reminder(reminder_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    reminder = await get_reminder(session, current_user.id, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@router.post("", response_model=ReminderRead)
async def create_new_reminder(reminder_in: ReminderCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_reminder(session, current_user.id, reminder_in)

@router.patch("/{reminder_id}", response_model=ReminderRead)
async def update_existing_reminder(reminder_id: UUID, reminder_in: ReminderUpdate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    reminder = await update_reminder(session, current_user.id, reminder_id, reminder_in)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder

@router.delete("/{reminder_id}")
async def delete_existing_reminder(reminder_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_reminder(session, current_user.id, reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {"ok": True}
