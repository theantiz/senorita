"""reconcile backend model schema

Revision ID: b6a4df3e91c2
Revises: 8f2c7b91d4a1
Create Date: 2026-08-19 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6a4df3e91c2"
down_revision: Union[str, None] = "8f2c7b91d4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_constraint_if_exists(table_name: str, constraint_name: str) -> None:
    op.execute(
        f"""
        ALTER TABLE {table_name}
        DROP CONSTRAINT IF EXISTS {constraint_name}
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS briefings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_briefings_type CHECK (type IN ('daily', 'end_of_day'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS message_modes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            scope VARCHAR NOT NULL,
            contact_id UUID NULL REFERENCES contacts(id) ON DELETE CASCADE,
            channel VARCHAR NULL,
            mode VARCHAR NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT check_message_mode_scope CHECK (scope IN ('global', 'contact')),
            CONSTRAINT check_message_mode_channel CHECK (channel IN ('gmail', 'slack')),
            CONSTRAINT check_message_mode_mode CHECK (
                mode IN ('draft_only', 'approval_required', 'trusted', 'autonomous')
            ),
            CONSTRAINT uq_message_mode UNIQUE (user_id, scope, contact_id, channel)
        )
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_users_briefing_detail_level'
                  AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT chk_users_briefing_detail_level
                CHECK (briefing_detail_level IN ('brief', 'standard', 'detailed')) NOT VALID;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_users_eod_briefing_detail_level'
                  AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT chk_users_eod_briefing_detail_level
                CHECK (eod_briefing_detail_level IN ('brief', 'standard', 'detailed')) NOT VALID;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'chk_email_direction'
                  AND conrelid = 'email_messages'::regclass
            ) THEN
                ALTER TABLE email_messages
                ADD CONSTRAINT chk_email_direction
                CHECK (direction IN ('inbound', 'outbound')) NOT VALID;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    _drop_constraint_if_exists("email_messages", "chk_email_direction")
    _drop_constraint_if_exists("users", "chk_users_eod_briefing_detail_level")
    _drop_constraint_if_exists("users", "chk_users_briefing_detail_level")
    op.execute("DROP TABLE IF EXISTS message_modes")
    op.execute("DROP TABLE IF EXISTS briefings")
