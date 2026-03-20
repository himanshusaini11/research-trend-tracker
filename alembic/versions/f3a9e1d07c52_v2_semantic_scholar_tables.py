"""v2: add semantic_scholar_id to papers, create paper_citations and paper_authors

Revision ID: f3a9e1d07c52
Revises: 2ce13f2f4f5f
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3a9e1d07c52"
down_revision: Union[str, Sequence[str], None] = "2ce13f2f4f5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

citation_type_enum = postgresql.ENUM("citation", "reference", name="citation_type_enum")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add semantic_scholar_id to papers (nullable, unique)
    # ------------------------------------------------------------------
    op.add_column(
        "papers",
        sa.Column("semantic_scholar_id", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_papers_semantic_scholar_id", "papers", ["semantic_scholar_id"]
    )

    # ------------------------------------------------------------------
    # 2. Create citation_type_enum Postgres ENUM (must exist before table)
    # ------------------------------------------------------------------
    citation_type_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 3. Create paper_citations
    # ------------------------------------------------------------------
    op.create_table(
        "paper_citations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_arxiv_id", sa.String(64), nullable=False),
        sa.Column("cited_paper_id", sa.String(64), nullable=False),
        sa.Column(
            "citation_type",
            postgresql.ENUM("citation", "reference", name="citation_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["source_arxiv_id"],
            ["papers.arxiv_id"],
            name="fk_paper_citations_source_arxiv_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "source_arxiv_id",
            "cited_paper_id",
            "citation_type",
            name="uq_paper_citations_src_cited_type",
        ),
    )
    op.create_index(
        "ix_paper_citations_source_arxiv_id", "paper_citations", ["source_arxiv_id"]
    )
    op.create_index(
        "ix_paper_citations_cited_paper_id", "paper_citations", ["cited_paper_id"]
    )

    # ------------------------------------------------------------------
    # 4. Create paper_authors
    # ------------------------------------------------------------------
    op.create_table(
        "paper_authors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("paper_id", sa.String(64), nullable=False),
        sa.Column("author_id", sa.String(64), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["papers.arxiv_id"],
            name="fk_paper_authors_paper_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_paper_author"),
    )
    op.create_index("ix_paper_authors_paper_id", "paper_authors", ["paper_id"])
    op.create_index("ix_paper_authors_author_id", "paper_authors", ["author_id"])


def downgrade() -> None:
    # Reverse order — drop dependents before parents
    op.drop_index("ix_paper_authors_author_id", table_name="paper_authors")
    op.drop_index("ix_paper_authors_paper_id", table_name="paper_authors")
    op.drop_table("paper_authors")

    op.drop_index("ix_paper_citations_cited_paper_id", table_name="paper_citations")
    op.drop_index("ix_paper_citations_source_arxiv_id", table_name="paper_citations")
    op.drop_table("paper_citations")

    citation_type_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_constraint("uq_papers_semantic_scholar_id", "papers", type_="unique")
    op.drop_column("papers", "semantic_scholar_id")
