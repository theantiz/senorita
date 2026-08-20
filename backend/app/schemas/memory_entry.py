from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MemoryEntryBase(BaseModel):
    content: str
    memory_type: str
    source_ref: str | None = None
    confidence: str | None = None
    importance_score: float | None = None
    locked: bool = False
    status: str = 'active'

class MemoryEntryCreate(MemoryEntryBase):
    pass

class MemoryEntryUpdate(BaseModel):
    content: str | None = None
    memory_type: str | None = None
    source_ref: str | None = None
    confidence: str | None = None
    importance_score: float | None = None
    locked: bool | None = None
    status: str | None = None

class MemoryEntryRead(MemoryEntryBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
