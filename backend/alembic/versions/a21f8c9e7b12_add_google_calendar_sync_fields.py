"""add_google_calendar_sync_fields

Revision ID: a21f8c9e7b12
Revises: d60b02f59d7f
Create Date: 2026-08-13

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a21f8c9e7b12"
down_revision: Union[str, None] = "d60b02f59d7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column("source", sa.Text(), server_default="manual", nullable=False),
    )
    op.add_column(
        "calendar_events",
        sa.Column("google_event_id", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "chk_calendar_events_source",
        "calendar_events",
        "source IN ('manual', 'google_calendar')",
    )
    op.create_unique_constraint(
        "uq_calendar_events_user_google_event_id",
        "calendar_events",
        ["user_id", "google_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_calendar_events_user_google_event_id",
        "calendar_events",
        type_="unique",
    )
    op.drop_constraint(
        "chk_calendar_events_source",
        "calendar_events",
        type_="check",
    )
    op.drop_column("calendar_events", "google_event_id")
    op.drop_column("calendar_events", "source")
