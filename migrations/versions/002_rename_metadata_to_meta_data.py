"""Rename metadata columns to meta_data

Revision ID: 002
Revises: 001
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename metadata to meta_data in both tables."""
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.alter_column('metadata', new_column_name='meta_data')
    with op.batch_alter_table('messages') as batch_op:
        batch_op.alter_column('metadata', new_column_name='meta_data')


def downgrade() -> None:
    """Rename meta_data back to metadata in both tables."""
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.alter_column('meta_data', new_column_name='metadata')
    with op.batch_alter_table('messages') as batch_op:
        batch_op.alter_column('meta_data', new_column_name='metadata')
