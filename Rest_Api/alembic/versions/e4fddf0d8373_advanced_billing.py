"""billing_columns_migration

Revision ID: e4fddf0d8373
Revises: 85d9ca8e9e3b
Create Date: 2026-04-12 18:46:20.543925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4fddf0d8373'
down_revision: Union[str, Sequence[str], None] = '85d9ca8e9e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('buckets', sa.Column('current_storage_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('buckets', sa.Column('ingress_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('buckets', sa.Column('egress_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('buckets', sa.Column('internal_transfer_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.drop_column('buckets', 'bandwidth_bytes')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('buckets', sa.Column('bandwidth_bytes', sa.Integer(), nullable=False, server_default='0'))
    op.drop_column('buckets', 'current_storage_bytes')
    op.drop_column('buckets', 'ingress_bytes')
    op.drop_column('buckets', 'egress_bytes')
    op.drop_column('buckets', 'internal_transfer_bytes')
