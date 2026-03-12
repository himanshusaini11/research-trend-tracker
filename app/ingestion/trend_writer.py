from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount, Paper
from app.ingestion.schemas import ArxivPaper, KeywordExtractionResult


class TrendWriter:
    def __init__(self, db_session: AsyncSession) -> None:
        self._session = db_session

    async def write_papers(self, papers: list[ArxivPaper]) -> tuple[int, int]:
        """Insert papers, skipping duplicates. Returns (new, skipped)."""
        if not papers:
            return 0, 0

        rows = [
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "abstract": p.abstract,
                "authors": p.authors,
                "categories": p.categories,
                "published_at": p.published_at,
                "ingested_at": datetime.now(UTC),
            }
            for p in papers
        ]

        stmt = (
            insert(Paper)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["arxiv_id"])
            .returning(Paper.id)
        )
        result = await self._session.execute(stmt)
        new_count = len(result.fetchall())
        skipped = len(papers) - new_count
        return new_count, skipped

    async def write_keywords(
        self,
        results: list[KeywordExtractionResult],
        window_date: date,
    ) -> int:
        """Upsert keyword counts for the given window date. Returns rows written."""
        if not results:
            return 0

        window_dt = datetime(
            window_date.year, window_date.month, window_date.day, tzinfo=UTC
        )

        # Flatten: one row per (keyword, category) pair
        # We derive category from the paper's categories via a separate lookup,
        # but since KeywordExtractionResult doesn't carry categories we use
        # a sentinel category "all" and let analytics split by category later.
        rows = [
            {"keyword": kw, "category": "all", "count": 1, "window_date": window_dt}
            for result in results
            for kw in result.keywords
        ]

        if not rows:
            return 0

        stmt = (
            insert(KeywordCount)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["keyword", "category", "window_date"],
                set_={"count": KeywordCount.count + 1},
            )
        )
        await self._session.execute(stmt)
        return len(rows)
