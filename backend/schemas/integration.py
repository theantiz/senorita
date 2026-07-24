from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class IntegrationBase(BaseModel):
    provider: str
    status: str
    scopes: list[str] = []
    permissions: dict = {}


class IntegrationRead(IntegrationBase):
    id: Optional[UUID] = None          # None for transient "disconnected" placeholders
    user_id: Optional[UUID] = None
    token_expires_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IntegrationUpdatePermissions(BaseModel):
    permissions: dict
