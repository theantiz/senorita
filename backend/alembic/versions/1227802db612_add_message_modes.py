"""add_message_modes

Revision ID: 1227802db612
Revises: 77df006c34e6
Create Date: 2026-07-26 20:27:13.501393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1227802db612'
down_revision: Union[str, None] = '77df006c34e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
