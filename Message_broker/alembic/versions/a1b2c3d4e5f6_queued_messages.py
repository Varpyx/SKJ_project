"""Pridani tabulky queued_messages

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Sequence[str] = ()
depends_on: Union[str, None] = ()


def upgrade() -> None:
    op.create_table(
        'queued_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('topic', sa.String(), index=True, nullable=False),
        sa.Column('payload', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_delivered', sa.Boolean(), default=False, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('queued_messages')