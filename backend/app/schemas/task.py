from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None
    priority: str | None = None
    status: str = "pending"
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
