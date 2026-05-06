"""create product_matches table

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 00:02:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_matches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email_id', sa.String(36), sa.ForeignKey('emails.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(100), nullable=False),
        sa.Column('title', sa.String(500)),
        sa.Column('score', sa.Float),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_product_matches_email_id', 'product_matches', ['email_id'])


def downgrade() -> None:
    op.drop_table('product_matches')
