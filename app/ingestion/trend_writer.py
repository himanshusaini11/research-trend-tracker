from __future__ import annotations

from collections import Counter
from datetime import date, datetime, UTC
from itertools import islice
from typing import Iterator

from sqlalchemy import select
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
        window_date: date,
        papers: list[ArxivPaper] | None = None,
    ) -> int:
        """Upsert keyword counts for the given window date. Returns rows written.

        If `papers` is provided, keywords are stored per the paper's actual
        arXiv categories. Without it they fall back to the sentinel "all".
        """
        if not results:
            return 0

        window_dt = datetime(
            window_date.year, window_date.month, window_date.day, tzinfo=UTC
        )

        # Build arxiv_id → categories map from the papers list (if provided)
        category_map: dict[str, list[str]] = {}
        if papers:
            for p in papers:
                category_map[p.arxiv_id] = p.categories or ["all"]

        # Aggregate counts — Counter avoids duplicate (keyword, category)
        # rows in the same INSERT which would trigger CardinalityViolationError.
        counter: Counter[tuple[str, str]] = Counter()
        for result in results:
            cats = category_map.get(result.arxiv_id, ["all"])
            for cat in cats:
                for kw in result.keywords:
                    counter[(kw, cat)] += 1

        if not counter:
            return 0

        rows = [
            {"keyword": kw, "category": cat, "count": cnt, "window_date": window_dt}
            for (kw, cat), cnt in counter.items()
        ]

        for batch in _batched(rows, _BATCH_SIZE):
            ins = insert(KeywordCount)
            stmt = ins.values(batch).on_conflict_do_update(
                index_elements=["keyword", "category", "window_date"],
                set_={"count": KeywordCount.count + ins.excluded.count},
            )
            await self._session.execute(stmt)
        return len(rows)
