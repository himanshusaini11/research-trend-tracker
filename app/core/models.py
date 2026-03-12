from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
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
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
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
        DateTime(timezone=True), nullable=False, index=True
    )
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_trend_scores_keyword_category", "keyword", "category"),
        Index("ix_trend_scores_window_start", "window_start"),
    )
