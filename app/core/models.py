from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (Index("ix_papers_categories", "categories", postgresql_using="gin"),)


class KeywordCount(Base):
    """Time-series table — partition as a TimescaleDB hypertable on window_date."""

    __tablename__ = "keyword_counts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("keyword", "category", "window_date", name="uq_keyword_counts_kw_cat_date"),
        Index("ix_keyword_counts_keyword_category", "keyword", "category"),
        Index("ix_keyword_counts_window_date", "window_date"),
    )


TrendDirection = Literal["rising", "falling", "stable"]


class TrendScore(Base):
    """Time-series table — partition as a TimescaleDB hypertable on window_start."""

    __tablename__ = "trend_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    trend_direction: Mapped[TrendDirection] = mapped_column(String(16), nullable=False)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("keyword", "category", "window_start", name="uq_trend_scores_kw_cat_start"),
        Index("ix_trend_scores_keyword_category", "keyword", "category"),
        Index("ix_trend_scores_window_start", "window_start"),
    )


CitationType = Literal["citation", "reference"]


class PaperCitation(Base):
    """Citation / reference edges fetched from Semantic Scholar."""

    __tablename__ = "paper_citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_arxiv_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.arxiv_id", ondelete="CASCADE"), nullable=False
    )
    cited_paper_id: Mapped[str] = mapped_column(String(64), nullable=False)
    citation_type: Mapped[CitationType] = mapped_column(
        Enum("citation", "reference", name="citation_type_enum"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_arxiv_id", "cited_paper_id", "citation_type",
            name="uq_paper_citations_src_cited_type",
        ),
        Index("ix_paper_citations_source_arxiv_id", "source_arxiv_id"),
        Index("ix_paper_citations_cited_paper_id", "cited_paper_id"),
    )


class PaperAuthor(Base):
    """Author records fetched from Semantic Scholar, linked by arXiv ID."""

    __tablename__ = "paper_authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("papers.arxiv_id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    author_name: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("paper_id", "author_id", name="uq_paper_authors_paper_author"),
        Index("ix_paper_authors_paper_id", "paper_id"),
        Index("ix_paper_authors_author_id", "author_id"),
    )
