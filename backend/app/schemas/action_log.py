from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
