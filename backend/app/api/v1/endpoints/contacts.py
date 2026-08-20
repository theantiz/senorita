from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.services.contact_service import create_contact, delete_contact, get_contact, get_contacts, update_contact

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactRead])
async def list_contacts(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_contacts(session, current_user.id)


@router.get("/{contact_id}", response_model=ContactRead)
async def read_contact(
    contact_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    contact = await get_contact(session, current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.post("", response_model=ContactRead)
async def create_new_contact(
    contact_in: ContactCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return await create_contact(session, current_user.id, contact_in)


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_existing_contact(
    contact_id: UUID,
    contact_in: ContactUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = await update_contact(session, current_user.id, contact_id, contact_in)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.delete("/{contact_id}")
async def delete_existing_contact(
    contact_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    success = await delete_contact(session, current_user.id, contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"ok": True}


@router.get("/{contact_id}/tone-profile")
async def get_tone_profile(
    contact_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    contact = await get_contact(session, current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact.tone_profile


@router.patch("/{contact_id}/tone-profile/{channel}")
async def update_tone_profile_channel(
    contact_id: UUID,
    channel: str,
    payload: dict,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually overrides the tone profile for a specific channel (e.g. 'email' or 'slack').
    This automatically sets user_override=True to prevent AI inference from clobbering it.
    """
    contact = await get_contact(session, current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    current_profiles = dict(contact.tone_profile)
    channel_profile = current_profiles.get(channel, {})

    # Merge payload
    channel_profile.update(payload)
    channel_profile["user_override"] = True

    current_profiles[channel] = channel_profile

    # We use update_contact to trigger the SQLAlchemy update and commit
    await update_contact(session, current_user.id, contact_id, ContactUpdate(tone_profile=current_profiles))

    return current_profiles
