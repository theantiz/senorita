"""Add daily_usage table for per-user cost control

Revision ID: 5740501778e1
Revises: 4435c236049b
Create Date: 2026-08-20 09:00:05.573906

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5740501778e1"
down_revision: Union[str, None] = "4435c236049b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the daily_usage table for per-user cost and token tracking
    op.create_table(
        "daily_usage",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("agent_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_invocations", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"),
    )
    op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"])
    op.create_index("ix_daily_usage_date", "daily_usage", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_usage_date", table_name="daily_usage")
    op.drop_index("ix_daily_usage_user_id", table_name="daily_usage")
    op.drop_table("daily_usage")
