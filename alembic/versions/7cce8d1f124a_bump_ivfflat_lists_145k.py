"""bump_ivfflat_lists_145k

Revision ID: 7cce8d1f124a
Revises: c8b267deac08
Create Date: 2026-03-29 02:25:35.058155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cce8d1f124a'
down_revision: Union[str, Sequence[str], None] = 'c8b267deac08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_paper_embeddings_embedding")
    op.execute("""
        CREATE INDEX ix_paper_embeddings_embedding
        ON paper_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 1000)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_paper_embeddings_embedding")
    op.execute("""
        CREATE INDEX ix_paper_embeddings_embedding
        ON paper_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """)

