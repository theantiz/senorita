from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from db.session import get_db
from db.models import User
from schemas.contact import ContactCreate, ContactUpdate, ContactRead
from services.contact_service import get_contacts, get_contact, create_contact, update_contact, delete_contact
from core.security import get_current_user

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.get("", response_model=list[ContactRead])
async def list_contacts(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_contacts(session, current_user.id)

@router.get("/{contact_id}", response_model=ContactRead)
async def read_contact(contact_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    contact = await get_contact(session, current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.post("", response_model=ContactRead)
async def create_new_contact(contact_in: ContactCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_contact(session, current_user.id, contact_in)

@router.patch("/{contact_id}", response_model=ContactRead)
async def update_existing_contact(contact_id: UUID, contact_in: ContactUpdate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    contact = await update_contact(session, current_user.id, contact_id, contact_in)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.delete("/{contact_id}")
async def delete_existing_contact(contact_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_contact(session, current_user.id, contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}
