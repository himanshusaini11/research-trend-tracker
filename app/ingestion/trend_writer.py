from __future__ import annotations

from collections import Counter
from datetime import datetime, UTC
from itertools import islice
from typing import Iterator

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount, Paper
from app.ingestion.schemas import ArxivPaper, KeywordExtractionResult


_BATCH_SIZE = 2_000  # stays well under asyncpg's 32 767-parameter limit


def _batched(lst: list, n: int) -> Iterator[list]:
    it = iter(lst)
    while chunk := list(islice(it, n)):
        yield chunk


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

        new_count = 0
        for batch in _batched(rows, _BATCH_SIZE):
            stmt = (
                insert(Paper)
                .values(batch)
                .on_conflict_do_nothing(index_elements=["arxiv_id"])
                .returning(Paper.id)
            )
            result = await self._session.execute(stmt)
            new_count += len(result.fetchall())
        skipped = len(papers) - new_count
        return new_count, skipped

    async def write_keywords(
        self,
        results: list[KeywordExtractionResult],
        window_date: datetime,
        papers: list[ArxivPaper] | None = None,
    ) -> int:
        """Upsert keyword counts. Returns total rows written.

        When `papers` is provided:
        - keywords are stored per the paper's actual arXiv categories
        - the bucket timestamp uses each paper's published_at (truncated to the
          1st of its publication month) for real TimescaleDB time-series granularity

        When `papers` is not provided, all keywords fall back to the `window_date`
        bucket and the "all" sentinel category.
        """
        if not results:
            return 0

        fallback_dt = datetime(
            window_date.year, window_date.month, window_date.day, tzinfo=UTC
        )

        # Build per-paper maps when paper metadata is available
        category_map: dict[str, list[str]] = {}
        date_map: dict[str, datetime] = {}
        if papers:
            for p in papers:
                category_map[p.arxiv_id] = p.categories or ["all"]
                # Truncate to first of publication month for consistent bucketing
                pub = p.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=UTC)
                date_map[p.arxiv_id] = pub.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )

        # Aggregate counts per (window_dt, keyword, category)
        dated_counter: dict[datetime, Counter[tuple[str, str]]] = {}
        for result in results:
            cats = category_map.get(result.arxiv_id, ["all"])
            wdt = date_map.get(result.arxiv_id, fallback_dt)
            bucket = dated_counter.setdefault(wdt, Counter())
            for cat in cats:
                for kw in result.keywords:
                    bucket[(kw, cat)] += 1

        total_rows = 0
        for wdt, counter in dated_counter.items():
            if not counter:
                continue
            rows = [
                {"keyword": kw, "category": cat, "count": cnt, "window_date": wdt}
                for (kw, cat), cnt in counter.items()
            ]
            for batch in _batched(rows, _BATCH_SIZE):
                ins = insert(KeywordCount)
                stmt = ins.values(batch).on_conflict_do_update(
                    index_elements=["keyword", "category", "window_date"],
                    set_={"count": KeywordCount.count + ins.excluded.count},
                )
                await self._session.execute(stmt)
            total_rows += len(rows)

        return total_rows
