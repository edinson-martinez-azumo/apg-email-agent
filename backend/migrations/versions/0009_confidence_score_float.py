"""change confidence_score to float

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('drafts', 'confidence_score',
                    type_=sa.Float(),
                    existing_type=sa.Integer(),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('drafts', 'confidence_score',
                    type_=sa.Integer(),
                    existing_type=sa.Float(),
                    existing_nullable=True)
