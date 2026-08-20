import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

class Cooldown(Base):
    __tablename__ = "cooldowns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    trigger_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    last_executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    cooldown_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
