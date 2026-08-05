from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

class MessageModeBase(BaseModel):
    scope: Literal['global', 'contact']
    contact_id: Optional[UUID] = None
    channel: Optional[Literal['gmail', 'slack']] = None
    mode: Literal['draft_only', 'approval_required', 'trusted', 'autonomous']

class MessageModeCreate(MessageModeBase):
    pass

class MessageModeUpdate(BaseModel):
    mode: Optional[Literal['draft_only', 'approval_required', 'trusted', 'autonomous']] = None

class MessageModeRead(MessageModeBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
