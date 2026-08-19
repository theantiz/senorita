"""create integrations table

Revision ID: 001_integrations
Revises:
Create Date: 2026-07-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_integrations"
down_revision: Union[str, None] = "000_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.Text,
            server_default="disconnected",
            nullable=False,
        ),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('gmail','whatsapp','slack','google_calendar','outlook',"
            "'apple_calendar','google_drive','linkedin')",
            name="chk_integrations_provider",
        ),
        sa.CheckConstraint(
            "status IN ('connected','disconnected','error','token_expired')",
            name="chk_integrations_status",
        ),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"])
    op.create_index(
        "ix_integrations_user_provider",
        "integrations",
        ["user_id", "provider"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_integrations_user_provider", table_name="integrations")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
