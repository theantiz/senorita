"""add tool invocations confirmations and idempotency

Revision ID: 8f2c7b91d4a1
Revises: 4f501da73b75
Create Date: 2026-08-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f2c7b91d4a1"
down_revision: Union[str, None] = "4f501da73b75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("tool_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("arguments_hash", sa.Text(), nullable=False),
        sa.Column("arguments_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False),
        sa.Column("confirmation_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.Text(), server_default="local", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'WAITING_CONFIRMATION', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="chk_tool_invocations_status",
        ),
        sa.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_tool_invocations_risk_level",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_invocations_request_id", "tool_invocations", ["request_id"], unique=False)
    op.create_index("ix_tool_invocations_conversation_id", "tool_invocations", ["conversation_id"], unique=False)
    op.create_index("ix_tool_invocations_user_id", "tool_invocations", ["user_id"], unique=False)
    op.create_index("ix_tool_invocations_tool_name", "tool_invocations", ["tool_name"], unique=False)
    op.create_index("ix_tool_invocations_status", "tool_invocations", ["status"], unique=False)
    op.create_index(
        "ix_tool_invocations_idempotency_key_hash", "tool_invocations", ["idempotency_key_hash"], unique=False
    )
    op.create_index("ix_tool_invocations_confirmation_id", "tool_invocations", ["confirmation_id"], unique=False)
    op.create_index("ix_tool_invocations_created_at", "tool_invocations", ["created_at"], unique=False)

    op.create_table(
        "tool_confirmations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column("tool_invocation_id", sa.UUID(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("arguments_preview", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED')",
            name="chk_tool_confirmations_status",
        ),
        sa.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_tool_confirmations_risk_level",
        ),
        sa.ForeignKeyConstraint(["tool_invocation_id"], ["tool_invocations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_invocation_id"),
    )
    op.create_index("ix_tool_confirmations_user_id", "tool_confirmations", ["user_id"], unique=False)
    op.create_index("ix_tool_confirmations_conversation_id", "tool_confirmations", ["conversation_id"], unique=False)
    op.create_index("ix_tool_confirmations_tool_name", "tool_confirmations", ["tool_name"], unique=False)
    op.create_index("ix_tool_confirmations_status", "tool_confirmations", ["status"], unique=False)
    op.create_index(
        "ix_tool_confirmations_tool_invocation_id", "tool_confirmations", ["tool_invocation_id"], unique=False
    )
    op.create_index("ix_tool_confirmations_created_at", "tool_confirmations", ["created_at"], unique=False)

    op.create_table(
        "tool_idempotency_keys",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column("tool_invocation_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'WAITING_CONFIRMATION', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED', 'EXPIRED')",
            name="chk_tool_idempotency_keys_status",
        ),
        sa.ForeignKeyConstraint(["tool_invocation_id"], ["tool_invocations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key_hash", name="uq_tool_idempotency_user_key_hash"),
    )
    op.create_index("ix_tool_idempotency_keys_user_id", "tool_idempotency_keys", ["user_id"], unique=False)
    op.create_index("ix_tool_idempotency_keys_status", "tool_idempotency_keys", ["status"], unique=False)
    op.create_index("ix_tool_idempotency_keys_key_hash", "tool_idempotency_keys", ["key_hash"], unique=False)
    op.create_index(
        "ix_tool_idempotency_keys_tool_invocation_id",
        "tool_idempotency_keys",
        ["tool_invocation_id"],
        unique=False,
    )
    op.create_index("ix_tool_idempotency_keys_created_at", "tool_idempotency_keys", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tool_idempotency_keys_status", table_name="tool_idempotency_keys")
    op.drop_index("ix_tool_idempotency_keys_created_at", table_name="tool_idempotency_keys")
    op.drop_index("ix_tool_idempotency_keys_tool_invocation_id", table_name="tool_idempotency_keys")
    op.drop_index("ix_tool_idempotency_keys_key_hash", table_name="tool_idempotency_keys")
    op.drop_index("ix_tool_idempotency_keys_user_id", table_name="tool_idempotency_keys")
    op.drop_table("tool_idempotency_keys")

    op.drop_index("ix_tool_confirmations_status", table_name="tool_confirmations")
    op.drop_index("ix_tool_confirmations_created_at", table_name="tool_confirmations")
    op.drop_index("ix_tool_confirmations_tool_invocation_id", table_name="tool_confirmations")
    op.drop_index("ix_tool_confirmations_tool_name", table_name="tool_confirmations")
    op.drop_index("ix_tool_confirmations_conversation_id", table_name="tool_confirmations")
    op.drop_index("ix_tool_confirmations_user_id", table_name="tool_confirmations")
    op.drop_table("tool_confirmations")

    op.drop_index("ix_tool_invocations_idempotency_key_hash", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_created_at", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_confirmation_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_status", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_tool_name", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_user_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_conversation_id", table_name="tool_invocations")
    op.drop_index("ix_tool_invocations_request_id", table_name="tool_invocations")
    op.drop_table("tool_invocations")
