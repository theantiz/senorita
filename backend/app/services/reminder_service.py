from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder
from app.schemas.reminder import ReminderCreate, ReminderUpdate


async def get_reminders(session: AsyncSession, user_id: UUID) -> list[Reminder]:
    stmt = select(Reminder).where(Reminder.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_reminder(session: AsyncSession, user_id: UUID, reminder_id: UUID) -> Reminder | None:
    stmt = select(Reminder).where(Reminder.user_id == user_id, Reminder.id == reminder_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def create_reminder(session: AsyncSession, user_id: UUID, reminder_in: ReminderCreate) -> Reminder:
    reminder = Reminder(user_id=user_id, **reminder_in.model_dump())
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def update_reminder(
    session: AsyncSession, user_id: UUID, reminder_id: UUID, reminder_in: ReminderUpdate
) -> Reminder | None:
    reminder = await get_reminder(session, user_id, reminder_id)
    if not reminder:
        return None
    for k, v in reminder_in.model_dump(exclude_unset=True).items():
        setattr(reminder, k, v)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def delete_reminder(session: AsyncSession, user_id: UUID, reminder_id: UUID) -> bool:
    reminder = await get_reminder(session, user_id, reminder_id)
    if not reminder:
        return False
    await session.delete(reminder)
    await session.commit()
    return True
