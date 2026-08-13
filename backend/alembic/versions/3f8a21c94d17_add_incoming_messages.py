"""Add incoming_messages table

Revision ID: 3f8a21c94d17
Revises: 1d9f89ba1a52
Create Date: 2026-07-25 11:20:00.000000

Creates the channel-agnostic incoming_messages queue table used by the
WhatsApp (and future) messaging integrations. Inbound messages from any
channel are written here by the webhook handler and consumed by the
async message processor worker.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f8a21c94d17"
down_revision: Union[str, None] = "1d9f89ba1a52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incoming_messages",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Channel identifier: 'whatsapp', 'sms', 'slack', 'email'
        sa.Column("channel", sa.Text(), nullable=False),
        # Sender identifier in the channel's native format (phone, email, user ID)
        sa.Column("sender_id", sa.Text(), nullable=False),
        # Raw inbound message text
        sa.Column("content", sa.Text(), nullable=False),
        # Processing lifecycle state
        sa.Column(
            "status",
            sa.Text(),
            server_default="pending",
            nullable=False,
        ),
        # Populated when status='error'
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "channel IN ('whatsapp', 'sms', 'slack', 'email')",
            name="chk_incoming_messages_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'error')",
            name="chk_incoming_messages_status",
        ),
    )

    # Index for the processor worker's polling query:
    #   WHERE status = 'pending' ORDER BY created_at ASC
    op.create_index(
        "ix_incoming_messages_status_created_at",
        "incoming_messages",
        ["status", "created_at"],
    )

    # Index for per-user message history queries
    op.create_index(
        "ix_incoming_messages_user_id",
        "incoming_messages",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_incoming_messages_user_id", table_name="incoming_messages")
    op.drop_index("ix_incoming_messages_status_created_at", table_name="incoming_messages")
    op.drop_table("incoming_messages")
