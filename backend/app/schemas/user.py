from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    name: str
    timezone: str
    autonomy_level: int = 2
    style_profile: dict = {}
    memory_capture_sensitivity: str = "conservative"


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
