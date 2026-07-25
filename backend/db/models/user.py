from sqlalchemy import String, Integer, Text, DateTime, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from db.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    autonomy_level: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    style_profile: Mapped[dict] = mapped_column(JSONB, server_default='{}', nullable=False)
    memory_capture_sensitivity: Mapped[str] = mapped_column(Text, server_default='conservative', nullable=False) # From Module 4
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint(memory_capture_sensitivity.in_(['off', 'conservative', 'proactive']), name='chk_users_memory_capture_sensitivity'),
    )

    # Relationships
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    memory_entries = relationship("MemoryEntry", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    calendar_events = relationship("CalendarEvent", back_populates="user", cascade="all, delete-orphan")
    action_logs = relationship("ActionLog", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    notification_logs = relationship("NotificationLog", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    incoming_messages = relationship("IncomingMessage", back_populates="user", cascade="all, delete-orphan")
