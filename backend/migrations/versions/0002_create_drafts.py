"""create drafts table

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'drafts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email_id', sa.String(36), sa.ForeignKey('emails.id', ondelete='CASCADE'), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('edited_body', sa.Text),
        sa.Column('approved_by', sa.String(255)),
        sa.Column('approved_at', sa.DateTime(timezone=True)),
        sa.Column('sent_at', sa.DateTime(timezone=True)),
        sa.Column('gmail_draft_id', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_drafts_email_id', 'drafts', ['email_id'])


def downgrade() -> None:
    op.drop_table('drafts')
