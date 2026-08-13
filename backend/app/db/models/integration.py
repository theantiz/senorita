import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        server_default="disconnected",
        nullable=False
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        server_default="[]",
        nullable=False
    )
    permissions: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}",
        nullable=False
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    user = relationship("User", back_populates="integrations")

    __table_args__ = (
        CheckConstraint(
            provider.in_([
                "gmail",

                "slack",
                "google_calendar",
                "outlook",
                "apple_calendar",
                "google_drive",
                "linkedin"
            ]),
            name="chk_integrations_provider"
        ),
        CheckConstraint(
            status.in_([
                "connected",
                "disconnected",
                "error",
                "token_expired"
            ]),
            name="chk_integrations_status"
        ),
    )
