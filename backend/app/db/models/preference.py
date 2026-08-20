import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    domain: Mapped[str] = mapped_column(String, nullable=False, index=True)  # e.g., 'communication', 'scheduling'
    preference: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., 'concise', 'morning meetings'

    confidence: Mapped[str] = mapped_column(String, nullable=False, server_default="MEDIUM")  # HIGH, MEDIUM, LOW
    strength: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")  # 0.0 to 1.0
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="observed")  # observed, explicit

    scope: Mapped[str] = mapped_column(String, server_default="general", nullable=False)
    status: Mapped[str] = mapped_column(String, server_default="ACTIVE", nullable=False)
    supersedes_preference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("preferences.id"), nullable=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding = mapped_column(Vector(3072), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="preferences")
