import os

SCHEMAS_DIR = "backend/schemas"
os.makedirs(SCHEMAS_DIR, exist_ok=True)

user_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class UserBase(BaseModel):
    name: str
    timezone: str
    autonomy_level: int = 2
    style_profile: dict = {}
    memory_capture_sensitivity: str = 'conservative'

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: str | None = None
    timezone: str | None = None
    autonomy_level: int | None = None
    style_profile: dict | None = None
    memory_capture_sensitivity: str | None = None

class UserRead(UserBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

contact_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ContactBase(BaseModel):
    name: str
    relationship_type: str
    tone_profile: dict = {}
    last_discussed_topic: str | None = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    name: str | None = None
    relationship_type: str | None = None
    tone_profile: dict | None = None
    last_discussed_topic: str | None = None

class ContactRead(ContactBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

memory_entry_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class MemoryEntryBase(BaseModel):
    content: str
    category: str
    source_ref: str | None = None
    confidence: float | None = None
    importance_score: float | None = None
    locked: bool = False
    status: str = 'active'

class MemoryEntryCreate(MemoryEntryBase):
    pass

class MemoryEntryUpdate(BaseModel):
    content: str | None = None
    category: str | None = None
    source_ref: str | None = None
    confidence: float | None = None
    importance_score: float | None = None
    locked: bool | None = None
    status: str | None = None

class MemoryEntryRead(MemoryEntryBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

task_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class TaskBase(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    status: str = 'pending'
    project: str | None = None
    contact_id: UUID | None = None
    reminder_id: UUID | None = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    status: str | None = None
    project: str | None = None
    contact_id: UUID | None = None
    reminder_id: UUID | None = None

class TaskRead(TaskBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

reminder_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ReminderBase(BaseModel):
    type: str
    trigger_payload: dict
    status: str = 'active'

class ReminderCreate(ReminderBase):
    pass

class ReminderUpdate(BaseModel):
    type: str | None = None
    trigger_payload: dict | None = None
    status: str | None = None

class ReminderRead(ReminderBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

calendar_event_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class CalendarEventBase(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    attendees: list = []
    source_calendar: str = 'local'
    conflict_flags: list = []
    surfaced: bool = False

class CalendarEventCreate(CalendarEventBase):
    pass

class CalendarEventUpdate(BaseModel):
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    attendees: list | None = None
    source_calendar: str | None = None
    conflict_flags: list | None = None
    surfaced: bool | None = None

class CalendarEventRead(CalendarEventBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

action_log_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ActionLogBase(BaseModel):
    action_type: str
    payload: dict
    result: str
    confirmed_by_user: bool = False

class ActionLogCreate(ActionLogBase):
    pass

class ActionLogUpdate(BaseModel):
    result: str | None = None
    confirmed_by_user: bool | None = None

class ActionLogRead(ActionLogBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

conversation_code = """from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class ConversationBase(BaseModel):
    gemini_interaction_id: str | None = None
    role: str
    content: str

class ConversationCreate(ConversationBase):
    pass

class ConversationRead(ConversationBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
"""

init_code = """from .user import UserCreate, UserUpdate, UserRead
from .contact import ContactCreate, ContactUpdate, ContactRead
from .memory_entry import MemoryEntryCreate, MemoryEntryUpdate, MemoryEntryRead
from .task import TaskCreate, TaskUpdate, TaskRead
from .reminder import ReminderCreate, ReminderUpdate, ReminderRead
from .calendar_event import CalendarEventCreate, CalendarEventUpdate, CalendarEventRead
from .action_log import ActionLogCreate, ActionLogUpdate, ActionLogRead
from .conversation import ConversationCreate, ConversationRead

__all__ = [
    "UserCreate", "UserUpdate", "UserRead",
    "ContactCreate", "ContactUpdate", "ContactRead",
    "MemoryEntryCreate", "MemoryEntryUpdate", "MemoryEntryRead",
    "TaskCreate", "TaskUpdate", "TaskRead",
    "ReminderCreate", "ReminderUpdate", "ReminderRead",
    "CalendarEventCreate", "CalendarEventUpdate", "CalendarEventRead",
    "ActionLogCreate", "ActionLogUpdate", "ActionLogRead",
    "ConversationCreate", "ConversationRead",
]
"""

files = {
    "user.py": user_code,
    "contact.py": contact_code,
    "memory_entry.py": memory_entry_code,
    "task.py": task_code,
    "reminder.py": reminder_code,
    "calendar_event.py": calendar_event_code,
    "action_log.py": action_log_code,
    "conversation.py": conversation_code,
    "__init__.py": init_code,
}

for name, content in files.items():
    with open(f"{SCHEMAS_DIR}/{name}", "w") as f:
        f.write(content)

import pathlib

old_mem = pathlib.Path(f"{SCHEMAS_DIR}/memory.py")
if old_mem.exists():
    old_mem.unlink()
old_chat = pathlib.Path(f"{SCHEMAS_DIR}/chat.py")
if old_chat.exists():
    old_chat.unlink()

print("Schemas rewritten successfully!")
