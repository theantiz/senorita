from sqlalchemy import ForeignKey, Text, DateTime, Boolean, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from db.base import Base

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attendees: Mapped[list] = mapped_column(JSONB, server_default='[]', nullable=False)
    source: Mapped[str] = mapped_column(Text, default='manual', server_default='manual', nullable=False)
    source_calendar: Mapped[str] = mapped_column(Text, default='local', nullable=False)
    google_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_flags: Mapped[list] = mapped_column(JSONB, server_default='[]', nullable=False)
    surfaced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # From Module 9
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="calendar_events")

    __table_args__ = (
        CheckConstraint(
            source.in_(["manual", "google_calendar"]),
            name="chk_calendar_events_source",
        ),
        UniqueConstraint(
            "user_id",
            "google_event_id",
            name="uq_calendar_events_user_google_event_id",
        ),
    )
