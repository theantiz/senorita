"""add_slack_messages

Revision ID: 77df006c34e6
Revises: 28ab3bb1f752
Create Date: 2026-07-26 17:04:40.026202

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '77df006c34e6'
down_revision: Union[str, None] = '28ab3bb1f752'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'slack_messages',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('slack_channel_id', sa.Text(), nullable=False),
        sa.Column('slack_message_ts', sa.Text(), nullable=False),
        sa.Column('channel_name', sa.Text(), nullable=True),
        sa.Column('from_user', sa.Text(), nullable=False),
        sa.Column('body_snippet', sa.Text(), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('needs_reply', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_slack_messages_slack_channel_id'), 'slack_messages', ['slack_channel_id'], unique=False)
    op.create_index(op.f('ix_slack_messages_slack_message_ts'), 'slack_messages', ['slack_message_ts'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_slack_messages_slack_message_ts'), table_name='slack_messages')
    op.drop_index(op.f('ix_slack_messages_slack_channel_id'), table_name='slack_messages')
    op.drop_table('slack_messages')
