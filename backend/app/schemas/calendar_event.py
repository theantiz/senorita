from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CalendarEventBase(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    attendees: list = []
    source: str = 'manual'
    source_calendar: str = 'local'
    google_event_id: str | None = None
    conflict_flags: list = []
    surfaced: bool = False

class CalendarEventCreate(CalendarEventBase):
    pass

class CalendarEventUpdate(BaseModel):
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    attendees: list | None = None
    source: str | None = None
    source_calendar: str | None = None
    google_event_id: str | None = None
    conflict_flags: list | None = None
    surfaced: bool | None = None

class CalendarEventRead(CalendarEventBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
