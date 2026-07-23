from pydantic import BaseModel, ConfigDict
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
