from sqlalchemy import ForeignKey, Text, DateTime, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from db.base import Base

class MessageMode(Base):
    __tablename__ = "message_modes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Scope: 'global' or 'contact'
    scope: Mapped[str] = mapped_column(String, nullable=False)
    
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True)
    
    # Null channel means "all channels" for this scope
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Mode: 'draft_only', 'approval_required', 'trusted', 'autonomous'
    mode: Mapped[str] = mapped_column(String, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            scope.in_(['global', 'contact']),
            name='check_message_mode_scope'
        ),
        CheckConstraint(
            channel.in_(['gmail', 'slack']),
            name='check_message_mode_channel'
        ),
        CheckConstraint(
            mode.in_(['draft_only', 'approval_required', 'trusted', 'autonomous']),
            name='check_message_mode_mode'
        ),
        UniqueConstraint('user_id', 'scope', 'contact_id', 'channel', name='uq_message_mode'),
    )

    user = relationship("User")
    contact = relationship("Contact")
