"""Fix text nullable

Revision ID: a820a2beed00
Revises: df5ef2501dd8
Create Date: 2025-12-21 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a820a2beed00'
down_revision: Union[str, Sequence[str], None] = 'df5ef2501dd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=False)
