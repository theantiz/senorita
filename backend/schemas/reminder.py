from pydantic import BaseModel, ConfigDict
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
