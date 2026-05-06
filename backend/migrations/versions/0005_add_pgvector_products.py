"""add pgvector product_embeddings table

Revision ID: 0005
Revises: 0004
Create Date: 2024-01-01 00:04:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector  # noqa: F401

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    op.create_table(
        'product_embeddings',
        sa.Column('sku', sa.String(100), primary_key=True),
        sa.Column('title', sa.String(500)),
        sa.Column('search_text', sa.Text),
        sa.Column('embedding', Vector(512), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # HNSW index — no warm-up required, good for concurrent reads
    op.execute(
        "CREATE INDEX ix_product_embeddings_hnsw "
        "ON product_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index('ix_product_embeddings_hnsw', table_name='product_embeddings')
    op.drop_table('product_embeddings')
