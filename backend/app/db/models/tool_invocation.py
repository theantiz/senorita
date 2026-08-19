import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    request_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    tool_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING", index=True)
    arguments_hash: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_snapshot: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False, server_default="local")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key_hash: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'WAITING_CONFIRMATION', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="chk_tool_invocations_status",
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_tool_invocations_risk_level",
        ),
        Index("ix_tool_invocations_confirmation_id", "confirmation_id"),
        Index("ix_tool_invocations_created_at", "created_at"),
    )

    user = relationship("User", back_populates="tool_invocations")


class ToolConfirmation(Base):
    __tablename__ = "tool_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    tool_invocation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_invocations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_preview: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED')",
            name="chk_tool_confirmations_status",
        ),
        CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_tool_confirmations_risk_level",
        ),
        Index("ix_tool_confirmations_tool_invocation_id", "tool_invocation_id"),
        Index("ix_tool_confirmations_created_at", "created_at"),
    )

    user = relationship("User", back_populates="tool_confirmations")
    invocation = relationship("ToolInvocation")


class ToolIdempotencyKey(Base):
    __tablename__ = "tool_idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    tool_invocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_invocations.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING", index=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "key_hash", name="uq_tool_idempotency_user_key_hash"),
        CheckConstraint(
            "status IN ('PENDING', 'WAITING_CONFIRMATION', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="chk_tool_idempotency_keys_status",
        ),
        Index("ix_tool_idempotency_keys_key_hash", "key_hash"),
        Index("ix_tool_idempotency_keys_tool_invocation_id", "tool_invocation_id"),
        Index("ix_tool_idempotency_keys_created_at", "created_at"),
    )

    user = relationship("User", back_populates="tool_idempotency_keys")
    invocation = relationship("ToolInvocation")
