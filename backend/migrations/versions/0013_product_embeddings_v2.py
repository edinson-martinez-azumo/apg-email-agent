"""product_embeddings_v2 with 1024-dim vectors and quality filter

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'product_embeddings_v2',
        sa.Column('sku', sa.String(100), primary_key=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('search_text', sa.Text, nullable=True),
        sa.Column('embedding', Vector(1024), nullable=True),
        sa.Column('type', sa.Text, nullable=True),
        sa.Column('materials', sa.Text, nullable=True),
        sa.Column('moq', sa.Text, nullable=True),
        sa.Column('capacities', sa.Text, nullable=True),
        sa.Column('price_base', sa.Text, nullable=True),
        sa.Column('price_10k', sa.Text, nullable=True),
        sa.Column('price_25k', sa.Text, nullable=True),
        sa.Column('price_50k', sa.Text, nullable=True),
        sa.Column('price_100k', sa.Text, nullable=True),
        sa.Column('in_stock', sa.Boolean, server_default='false', nullable=True),
        sa.Column('image_url', sa.Text, nullable=True),
        sa.Column('dimensions', sa.Text, nullable=True),
        sa.Column('search_vector', sa.Text, nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )
    op.execute("""
        ALTER TABLE product_embeddings_v2
        ADD COLUMN search_vector_ts tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(search_vector, ''))) STORED
    """)
    op.create_index(
        'ix_product_embeddings_v2_search_vector',
        'product_embeddings_v2',
        ['search_vector_ts'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_table('product_embeddings_v2')
