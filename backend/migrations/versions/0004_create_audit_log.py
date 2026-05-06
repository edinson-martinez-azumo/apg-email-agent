"""create audit_log table

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-01 00:03:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email_id', sa.String(36), sa.ForeignKey('emails.id', ondelete='SET NULL')),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('actor', sa.String(255)),
        sa.Column('detail', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_log_email_id', 'audit_log', ['email_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])


def downgrade() -> None:
    op.drop_table('audit_log')
