import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SlackMessage(Base):
    __tablename__ = "slack_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    slack_channel_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    slack_message_ts: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)

    channel_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_user: Mapped[str] = mapped_column(Text, nullable=False)
    body_snippet: Mapped[str] = mapped_column(Text, nullable=False)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    needs_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
