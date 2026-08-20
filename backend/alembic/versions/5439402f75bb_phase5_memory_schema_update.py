"""phase5_memory_schema_update

Revision ID: 5439402f75bb
Revises: 5740501778e1
Create Date: 2026-08-20 09:41:18.635832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5439402f75bb'
down_revision: Union[str, None] = '5740501778e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename category to memory_type
    op.alter_column('memory_entries', 'category', new_column_name='memory_type')
    
    # Add updated_at
    op.add_column('memory_entries', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    
    # Cast confidence to Text
    op.execute("ALTER TABLE memory_entries ALTER COLUMN confidence TYPE text USING (CASE WHEN confidence > 0.66 THEN 'HIGH' WHEN confidence > 0.33 THEN 'MEDIUM' ELSE 'LOW' END)")


def downgrade() -> None:
    # Cast confidence back to Float
    op.execute("ALTER TABLE memory_entries ALTER COLUMN confidence TYPE double precision USING (CASE WHEN confidence = 'HIGH' THEN 1.0 WHEN confidence = 'MEDIUM' THEN 0.5 ELSE 0.0 END)")
    
    # Drop updated_at
    op.drop_column('memory_entries', 'updated_at')
    
    # Rename memory_type back to category
    op.alter_column('memory_entries', 'memory_type', new_column_name='category')
