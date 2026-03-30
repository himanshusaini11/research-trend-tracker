"""add_paper_embeddings_table

Revision ID: c8b267deac08
Revises: 2323bc3b4eba
Create Date: 2026-03-29 00:40:53.565541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b267deac08'
down_revision: Union[str, Sequence[str], None] = '2323bc3b4eba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        CREATE TABLE paper_embeddings (
            paper_id    INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
            embedding   vector(1024) NOT NULL,
            embedded_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("""
        CREATE INDEX ix_paper_embeddings_embedding
        ON paper_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_embeddings")
