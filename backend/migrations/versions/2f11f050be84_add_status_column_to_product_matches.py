"""add_status_column_to_product_matches

Revision ID: 2f11f050be84
Revises: fcecb146a1ac
Create Date: 2026-05-18 17:17:51.013093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2f11f050be84'
down_revision: Union[str, None] = 'fcecb146a1ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product_matches', sa.Column('status', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('product_matches', 'status')
