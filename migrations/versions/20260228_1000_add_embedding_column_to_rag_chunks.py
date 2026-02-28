"""add embedding column to rag_chunks

Revision ID: 20260228_1000
Revises: 20260228_0236_203b07bc02cc
Create Date: 2026-02-28 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260228_1000'
down_revision: Union[str, None] = '20260228_0236_203b07bc02cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add embedding column to rag_chunks table."""
    # Add embedding column as BLOB to store float32 array
    op.add_column(
        'rag_chunks',
        sa.Column('embedding', sa.LargeBinary, nullable=True)
    )

    # Create index on embedding for faster lookups (optional, depends on SQLite version)
    # Note: SQLite doesn't support vector indexes natively, so we rely on cosine similarity in Python


def downgrade() -> None:
    """Remove embedding column from rag_chunks table."""
    op.drop_column('rag_chunks', 'embedding')
