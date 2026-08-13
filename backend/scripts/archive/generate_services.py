import os

SERVICES_DIR = "backend/services"
os.makedirs(SERVICES_DIR, exist_ok=True)

contact_code = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
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
"""

task_code = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.db.models import Task
from app.schemas.task import TaskCreate, TaskUpdate

async def get_tasks(session: AsyncSession, user_id: UUID) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> Task | None:
    stmt = select(Task).where(Task.user_id == user_id, Task.id == task_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_task(session: AsyncSession, user_id: UUID, task_in: TaskCreate) -> Task:
    task = Task(user_id=user_id, **task_in.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task

async def update_task(session: AsyncSession, user_id: UUID, task_id: UUID, task_in: TaskUpdate) -> Task | None:
    task = await get_task(session, user_id, task_id)
    if not task:
        return None
    for k, v in task_in.model_dump(exclude_unset=True).items():
        setattr(task, k, v)
    await session.commit()
    await session.refresh(task)
    return task

async def delete_task(session: AsyncSession, user_id: UUID, task_id: UUID) -> bool:
    task = await get_task(session, user_id, task_id)
    if not task:
        return False
    await session.delete(task)
    await session.commit()
    return True
"""

reminder_code = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
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

async def update_reminder(session: AsyncSession, user_id: UUID, reminder_id: UUID, reminder_in: ReminderUpdate) -> Reminder | None:
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
"""

calendar_code = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.db.models import CalendarEvent
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate

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
"""

memory_code = """from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.db.models import MemoryEntry
from app.schemas.memory_entry import MemoryEntryCreate, MemoryEntryUpdate

async def get_memories(session: AsyncSession, user_id: UUID, category: str | None = None) -> list[MemoryEntry]:
    stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
    if category:
        stmt = stmt.where(MemoryEntry.category == category)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> MemoryEntry | None:
    stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id, MemoryEntry.id == memory_id)
    result = await session.execute(stmt)
    return result.scalars().first()

async def create_memory(session: AsyncSession, user_id: UUID, memory_in: MemoryEntryCreate) -> MemoryEntry:
    memory = MemoryEntry(user_id=user_id, **memory_in.model_dump())
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory

async def update_memory(session: AsyncSession, user_id: UUID, memory_id: UUID, memory_in: MemoryEntryUpdate) -> MemoryEntry | None:
    memory = await get_memory(session, user_id, memory_id)
    if not memory:
        return None
    for k, v in memory_in.model_dump(exclude_unset=True).items():
        setattr(memory, k, v)
    await session.commit()
    await session.refresh(memory)
    return memory

async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> bool:
    memory = await get_memory(session, user_id, memory_id)
    if not memory:
        return False
    await session.delete(memory)
    await session.commit()
    return True
"""

files = {
    "contact_service.py": contact_code,
    "task_service.py": task_code,
    "reminder_service.py": reminder_code,
    "calendar_service.py": calendar_code,
    "memory_service.py": memory_code,
}

for name, content in files.items():
    with open(f"{SERVICES_DIR}/{name}", "w") as f:
        f.write(content)

print("Services rewritten successfully!")
