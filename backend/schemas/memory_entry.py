from pydantic import BaseModel, ConfigDict
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
