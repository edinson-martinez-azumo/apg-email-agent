"""create emails table

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'emails',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('gmail_id', sa.String(255), nullable=False, unique=True),
        sa.Column('from_email', sa.String(255), nullable=False),
        sa.Column('from_name', sa.String(255)),
        sa.Column('subject', sa.String(500)),
        sa.Column('body_text', sa.Text),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_emails_status', 'emails', ['status'])
    op.create_index('ix_emails_received_at', 'emails', ['received_at'])


def downgrade() -> None:
    op.drop_table('emails')
