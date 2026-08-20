import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

class AutonomyPolicy(Base):
    __tablename__ = "autonomy_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    action_scope: Mapped[str] = mapped_column(String, nullable=False, index=True) # e.g. "gmail.send_email" or "calendar.*"
    autonomy_level: Mapped[str] = mapped_column(String, nullable=False) # SUGGEST, CONFIRM, TRUSTED, FULL_AUTO
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
