import os

API_DIR = "backend/api"
os.makedirs(API_DIR, exist_ok=True)

auth_code = """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import secrets
import hashlib
from uuid import UUID

from app.db.session import get_db
from app.db.models import User, AuthToken

router = APIRouter(prefix="/auth", tags=["auth"])

class SetupRequest(BaseModel):
    name: str
    timezone: str

@router.post("/setup")
async def setup_auth(request: SetupRequest, session: AsyncSession = Depends(get_db)):
    stmt = select(User)
    result = await session.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    # Create User
    new_user = User(
        name=request.name,
        timezone=request.timezone
    )
    session.add(new_user)
    await session.flush()

    # Generate token
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    auth_token = AuthToken(
        user_id=new_user.id,
        token_hash=token_hash
    )
    session.add(auth_token)
    await session.commit()

    return {"token": raw_token}
"""

security_code = """from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
from uuid import UUID

from app.db.session import get_db
from app.db.models import User, AuthToken

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db)
) -> User:
    raw_token = credentials.credentials
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    stmt = select(AuthToken).where(AuthToken.token_hash == token_hash)
    result = await session.execute(stmt)
    auth_token = result.scalars().first()

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt_user = select(User).where(User.id == auth_token.user_id)
    result_user = await session.execute(stmt_user)
    user = result_user.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return user
"""

contacts_route_code = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.schemas.contact import ContactCreate, ContactUpdate, ContactRead
from app.services.contact_service import get_contacts, get_contact, create_contact, update_contact, delete_contact
from app.core.security import get_current_user

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
"""

tasks_route_code = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.schemas.task import TaskCreate, TaskUpdate, TaskRead
from app.services.task_service import get_tasks, get_task, create_task, update_task, delete_task
from app.core.security import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("", response_model=list[TaskRead])
async def list_tasks(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_tasks(session, current_user.id)

@router.get("/{task_id}", response_model=TaskRead)
async def read_task(task_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = await get_task(session, current_user.id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("", response_model=TaskRead)
async def create_new_task(task_in: TaskCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_task(session, current_user.id, task_in)

@router.patch("/{task_id}", response_model=TaskRead)
async def update_existing_task(task_id: UUID, task_in: TaskUpdate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = await update_task(session, current_user.id, task_id, task_in)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/{task_id}")
async def delete_existing_task(task_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_task(session, current_user.id, task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}
"""

reminders_route_code = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.schemas.reminder import ReminderCreate, ReminderUpdate, ReminderRead
from app.services.reminder_service import get_reminders, get_reminder, create_reminder, update_reminder, delete_reminder
from app.core.security import get_current_user

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
"""

calendar_route_code = """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.schemas.calendar_event import CalendarEventCreate, CalendarEventUpdate, CalendarEventRead
from app.services.calendar_service import get_calendar_events, get_calendar_event, create_calendar_event, update_calendar_event, delete_calendar_event
from app.core.security import get_current_user

router = APIRouter(prefix="/calendar/events", tags=["calendar"])

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
"""

memory_route_code = """from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.db.models import User
from app.schemas.memory_entry import MemoryEntryCreate, MemoryEntryRead
from app.services.memory_service import get_memories, get_memory, create_memory, delete_memory
from app.core.security import get_current_user

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("", response_model=list[MemoryEntryRead])
async def list_memories(category: str | None = Query(None), session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_memories(session, current_user.id, category=category)

@router.post("", response_model=MemoryEntryRead)
async def create_new_memory(memory_in: MemoryEntryCreate, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await create_memory(session, current_user.id, memory_in)

@router.delete("/{memory_id}")
async def delete_existing_memory(memory_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    success = await delete_memory(session, current_user.id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True}

@router.patch("/{memory_id}/lock", response_model=MemoryEntryRead)
async def toggle_memory_lock(memory_id: UUID, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    memory = await get_memory(session, current_user.id, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    memory.locked = not memory.locked
    await session.commit()
    await session.refresh(memory)
    return memory
"""

activity_route_code = """from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.db.models import User, ActionLog
from app.schemas.action_log import ActionLogRead
from app.core.security import get_current_user

router = APIRouter(prefix="/activity", tags=["activity"])

@router.get("", response_model=List[ActionLogRead])
async def list_activity(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    stmt = select(ActionLog).where(ActionLog.user_id == current_user.id).order_by(ActionLog.created_at.desc()).limit(50)
    result = await session.execute(stmt)
    return list(result.scalars().all())
"""

chat_route_code = """from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Dict

from app.db.session import get_db
from app.db.models import User
from app.core.security import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

@router.post("")
async def chat_endpoint(request: ChatRequest, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Orchestrator goes here (Module 3)
    return {"response": f"Acknowledged: {request.message}"}
"""

files = {
    "routes_auth.py": auth_code,
    "routes_contacts.py": contacts_route_code,
    "routes_tasks.py": tasks_route_code,
    "routes_reminders.py": reminders_route_code,
    "routes_calendar.py": calendar_route_code,
    "routes_memory.py": memory_route_code,
    "routes_activity.py": activity_route_code,
    "routes_chat.py": chat_route_code,
}

for name, content in files.items():
    with open(f"{API_DIR}/{name}", "w") as f:
        f.write(content)

with open("backend/core/security.py", "w") as f:
    f.write(security_code)

print("API Routes rewritten successfully!")
