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
    """No-op migration; original text-nullable change was done in df5ef2501dd8."""
    pass


def downgrade() -> None:
    """No-op downgrade corresponding to the no-op upgrade."""
    pass
