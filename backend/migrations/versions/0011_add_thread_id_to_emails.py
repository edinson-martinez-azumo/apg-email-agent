"""add thread_id to emails

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('emails', sa.Column('thread_id', sa.String(255), nullable=True))
    op.create_index('ix_emails_thread_id', 'emails', ['thread_id'])


def downgrade() -> None:
    op.drop_index('ix_emails_thread_id', 'emails')
    op.drop_column('emails', 'thread_id')
