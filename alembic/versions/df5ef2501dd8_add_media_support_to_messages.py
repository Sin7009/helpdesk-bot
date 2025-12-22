"""Add media support to messages

Revision ID: df5ef2501dd8
Revises: ee07542f6c53
Create Date: 2025-12-21 19:15:05.549092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df5ef2501dd8'
down_revision: Union[str, Sequence[str], None] = 'ee07542f6c53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Split into two steps to avoid circular dependency in batch mode logic?
    # Or just add columns simply first, then do the alter batch.

    # 1. Add columns (SQLite allows adding nullable columns without batch)
    op.add_column('messages', sa.Column('content_type', sa.String(length=20), server_default="text", nullable=False))
    op.add_column('messages', sa.Column('media_id', sa.String(length=255), nullable=True))

    # 2. Modify 'text' to be nullable using batch mode
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('text',
               existing_type=sa.TEXT(),
               nullable=False)

        batch_op.drop_column('media_id')
        batch_op.drop_column('content_type')
