import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class AgentPlan(Base):
    __tablename__ = "agent_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="CREATED", index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'VALIDATING', 'RUNNING', 'WAITING_FOR_CONFIRMATION', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="chk_agent_plans_status",
        ),
    )

    user = relationship("User")
    steps = relationship("AgentPlanStep", back_populates="plan", cascade="all, delete-orphan", order_by="AgentPlanStep.created_at")


class AgentPlanStep(Base):
    __tablename__ = "agent_plan_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSONB, server_default="[]", nullable=False)
    execution_mode: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="CREATED")

    # Link to the actual invocation that occurred, if any.
    invocation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_invocations.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED')",
            name="chk_agent_plan_steps_status",
        ),
    )

    plan = relationship("AgentPlan", back_populates="steps")
    invocation = relationship("ToolInvocation")
