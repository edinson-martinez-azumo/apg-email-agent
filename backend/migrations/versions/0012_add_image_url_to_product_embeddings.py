"""add image_url and dimensions to product_embeddings

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-07
"""
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('ALTER TABLE product_embeddings ADD COLUMN IF NOT EXISTS image_url TEXT')
    op.execute('ALTER TABLE product_embeddings ADD COLUMN IF NOT EXISTS dimensions TEXT')


def downgrade() -> None:
    op.execute('ALTER TABLE product_embeddings DROP COLUMN IF EXISTS image_url')
    op.execute('ALTER TABLE product_embeddings DROP COLUMN IF EXISTS dimensions')
