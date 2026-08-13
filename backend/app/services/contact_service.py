from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contact
from app.schemas.contact import ContactCreate, ContactUpdate


async def get_contacts(session: AsyncSession, user_id: UUID) -> list[Contact]:
    stmt = select(Contact).where(Contact.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_contact(session: AsyncSession, user_id: UUID, contact_id: UUID) -> Contact | None:
    stmt = select(Contact).where(Contact.user_id == user_id, Contact.id == contact_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_contact(session: AsyncSession, user_id: UUID, contact_in: ContactCreate) -> Contact:
    contact = Contact(user_id=user_id, **contact_in.model_dump())
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact

async def update_contact(session: AsyncSession, user_id: UUID, contact_id: UUID, contact_in: ContactUpdate) -> Contact | None:
    contact = await get_contact(session, user_id, contact_id)
    if not contact:
        return None
    for k, v in contact_in.model_dump(exclude_unset=True).items():
        setattr(contact, k, v)
    await session.commit()
    await session.refresh(contact)
    return contact

async def delete_contact(session: AsyncSession, user_id: UUID, contact_id: UUID) -> bool:
    contact = await get_contact(session, user_id, contact_id)
    if not contact:
        return False
    await session.delete(contact)
    await session.commit()
    return True
