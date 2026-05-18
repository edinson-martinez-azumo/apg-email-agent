"""add_email_reference_fields

Revision ID: fcecb146a1ac
Revises: 0013
Create Date: 2026-05-18 10:42:17.794660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcecb146a1ac'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('emails', sa.Column('message_id', sa.String(length=500), nullable=True))
    op.add_column('emails', sa.Column('in_reply_to', sa.String(length=500), nullable=True))
    op.add_column('emails', sa.Column('references', sa.Text(), nullable=True))
    op.create_index(op.f('ix_emails_message_id'), 'emails', ['message_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_emails_message_id'), table_name='emails')
    op.drop_column('emails', 'references')
    op.drop_column('emails', 'in_reply_to')
    op.drop_column('emails', 'message_id')
