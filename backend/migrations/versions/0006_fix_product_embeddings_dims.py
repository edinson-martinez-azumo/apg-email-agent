"""fix product_embeddings vector dims 512->384 (Cohere embed-english-light-v3.0)

Revision ID: 0006
Revises: 0005
Create Date: 2024-01-01 00:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector  # noqa: F401

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('product_embeddings')

    op.create_table(
        'product_embeddings',
        sa.Column('sku', sa.String(100), primary_key=True),
        sa.Column('title', sa.String(500)),
        sa.Column('search_text', sa.Text),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.execute(
        "CREATE INDEX ix_product_embeddings_hnsw "
        "ON product_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_table('product_embeddings')

    op.create_table(
        'product_embeddings',
        sa.Column('sku', sa.String(100), primary_key=True),
        sa.Column('title', sa.String(500)),
        sa.Column('search_text', sa.Text),
        sa.Column('embedding', Vector(512), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.execute(
        "CREATE INDEX ix_product_embeddings_hnsw "
        "ON product_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
