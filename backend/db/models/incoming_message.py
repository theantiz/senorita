"""
db/models/incoming_message.py

Channel-agnostic message queue table.

All inbound messages — regardless of channel — are written here by the
webhook handler and consumed by workers/messaging/processor.py.
This decouples message ingestion (fast, < 20ms webhook ack) from
AI processing (slow, 1-5s per message).

Adding a new channel (SMS, Slack, etc.) requires:
  - A new webhook route that writes an IncomingMessage row
  - A new Sender class in integrations/
  - A new dispatch branch in the processor worker
  Nothing else changes.
"""

from sqlalchemy import ForeignKey, Text, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from db.base import Base


class IncomingMessage(Base):
    __tablename__ = "incoming_messages"

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
    # Channel that delivered this message
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    # Sender identifier in the channel's native format:
    #   whatsapp → E.164 phone number e.g. "+919876543210"
    #   email    → "user@example.com"
    #   slack    → Slack user ID "U012AB3CD"
    sender_id: Mapped[str] = mapped_column(Text, nullable=False)
    # Raw message body (text only; media will be transcribed upstream)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Processing lifecycle:
    #   pending    → row inserted, not yet picked up by worker
    #   processing → worker has locked this row and is working on it
    #   done       → AI reply sent successfully
    #   error      → processing failed; see `error` column for details
    status: Mapped[str] = mapped_column(
        Text,
        server_default="pending",
        nullable=False
    )
    # Populated when status='error'
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    user = relationship("User", back_populates="incoming_messages")

    __table_args__ = (
        CheckConstraint(
            channel.in_(["whatsapp", "sms", "slack", "email"]),
            name="chk_incoming_messages_channel"
        ),
        CheckConstraint(
            status.in_(["pending", "processing", "done", "error"]),
            name="chk_incoming_messages_status"
        ),
    )
