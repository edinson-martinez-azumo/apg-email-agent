"""add metadata + tsvector to product_embeddings

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('product_embeddings', sa.Column('type', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('materials', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('moq', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('capacities', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('price_base', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('price_10k', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('price_25k', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('price_50k', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('price_100k', sa.Text(), nullable=True))
    op.add_column('product_embeddings', sa.Column('in_stock', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('product_embeddings', sa.Column('search_vector', sa.Text(), nullable=True))
    op.execute("ALTER TABLE product_embeddings ADD COLUMN IF NOT EXISTS search_vector_ts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_vector, ''))) STORED")
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_embeddings_search_vector ON product_embeddings USING GIN (search_vector_ts)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_product_embeddings_search_vector")
    op.drop_column('product_embeddings', 'search_vector_ts')
    op.drop_column('product_embeddings', 'search_vector')
    op.drop_column('product_embeddings', 'in_stock')
    op.drop_column('product_embeddings', 'price_100k')
    op.drop_column('product_embeddings', 'price_50k')
    op.drop_column('product_embeddings', 'price_25k')
    op.drop_column('product_embeddings', 'price_10k')
    op.drop_column('product_embeddings', 'price_base')
    op.drop_column('product_embeddings', 'capacities')
    op.drop_column('product_embeddings', 'moq')
    op.drop_column('product_embeddings', 'materials')
    op.drop_column('product_embeddings', 'type')
