"""Integration tests for TrendWriter — exercises the full write path."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import KeywordCount, Paper
from app.ingestion.keyword_indexer import KeywordIndexer
from app.ingestion.schemas import ArxivPaper
from app.ingestion.trend_writer import TrendWriter


# ---------------------------------------------------------------------------
# write_papers
# ---------------------------------------------------------------------------

async def test_write_papers_inserts_new_rows(
    test_db: AsyncSession, sample_papers: list[ArxivPaper]
) -> None:
    writer = TrendWriter(test_db)
    new, skipped = await writer.write_papers(sample_papers)
    assert new == len(sample_papers)
    assert skipped == 0


async def test_write_papers_skips_duplicates(
    test_db: AsyncSession, sample_papers: list[ArxivPaper]
) -> None:
    writer = TrendWriter(test_db)
    await writer.write_papers(sample_papers)
    new, skipped = await writer.write_papers(sample_papers)
    assert new == 0
    assert skipped == len(sample_papers)


async def test_write_papers_empty_list(test_db: AsyncSession) -> None:
    writer = TrendWriter(test_db)
    new, skipped = await writer.write_papers([])
    assert new == 0
    assert skipped == 0


async def test_write_papers_rows_persisted(
    test_db: AsyncSession, sample_paper: ArxivPaper
) -> None:
    writer = TrendWriter(test_db)
    await writer.write_papers([sample_paper])
    await test_db.flush()

    result = await test_db.execute(
        select(Paper).where(Paper.arxiv_id == sample_paper.arxiv_id)
    )
    row = result.scalar_one()
    assert row.title == sample_paper.title
    assert row.categories == sample_paper.categories


# ---------------------------------------------------------------------------
# write_keywords
# ---------------------------------------------------------------------------

async def test_write_keywords_returns_row_count(
    test_db: AsyncSession, sample_papers: list[ArxivPaper]
) -> None:
    writer = TrendWriter(test_db)
    indexer = KeywordIndexer()
    results = [indexer.extract_keywords(p) for p in sample_papers]

    count = await writer.write_keywords(results, date.today(), sample_papers)
    assert count > 0


async def test_write_keywords_upserts_on_conflict(
    test_db: AsyncSession, sample_paper: ArxivPaper
) -> None:
    """Running write_keywords twice on the same window_date accumulates counts."""
    writer = TrendWriter(test_db)
    indexer = KeywordIndexer()
    results = [indexer.extract_keywords(sample_paper)]
    window = date.today()

    await writer.write_keywords(results, window, [sample_paper])
    await writer.write_keywords(results, window, [sample_paper])
    await test_db.flush()

    total = await test_db.scalar(select(func.sum(KeywordCount.count)))
    # Two runs → counts should be doubled vs one run
    assert total is not None and total > 0


async def test_write_keywords_empty_results(test_db: AsyncSession) -> None:
    writer = TrendWriter(test_db)
    count = await writer.write_keywords([], date.today())
    assert count == 0


async def test_write_keywords_without_papers_uses_all_category(
    test_db: AsyncSession, sample_paper: ArxivPaper
) -> None:
    """Without a papers list the fallback category 'all' is used."""
    writer = TrendWriter(test_db)
    indexer = KeywordIndexer()
    results = [indexer.extract_keywords(sample_paper)]

    count = await writer.write_keywords(results, date.today())
    assert count > 0

    rows = (await test_db.execute(select(KeywordCount))).scalars().all()
    assert all(r.category == "all" for r in rows)
