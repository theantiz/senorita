from pydantic import BaseModel, ConfigDict
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
