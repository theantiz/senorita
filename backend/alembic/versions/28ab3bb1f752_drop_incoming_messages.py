"""drop_incoming_messages

Revision ID: 28ab3bb1f752
Revises: 3f8a21c94d17
Create Date: 2026-07-26 16:59:41.770630

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '28ab3bb1f752'
down_revision: Union[str, None] = '3f8a21c94d17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('incoming_messages')

def downgrade() -> None:
    pass
