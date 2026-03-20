"""Backfill historical arXiv papers for a date range.

Usage:
    uv run python scripts/backfill_historical.py \\
        --start-date 2024-10-01 \\
        --end-date   2024-12-31 \\
        --categories cs.CL,cs.AI
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.models import PaperAuthor, PaperCitation
from app.ingestion.arxiv_client import ArxivClient
from app.ingestion.keyword_indexer import KeywordIndexer
from app.ingestion.schemas import ArxivPaper
from app.ingestion.trend_writer import TrendWriter
from app.ingestion.semantic_scholar import SemanticScholarClient

from sqlalchemy.dialects.postgresql import insert

_BASE_URL = "https://export.arxiv.org/api/query"
_BATCH_SIZE = 2_000


def _batched(items: list, size: int):  # type: ignore[type-arg]
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _fetch_date_range(
    categories: list[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 500,
    delay_seconds: float = 3.0,
) -> list[ArxivPaper]:
    """Fetch arXiv papers within [start_date, end_date] for the given categories."""
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    # Use ArxivClient for its feed parser only
    client = ArxivClient(
        categories=categories,
        max_results=max_results,
        delay_seconds=delay_seconds,
    )
    papers: dict[str, ArxivPaper] = {}

    async with httpx.AsyncClient(timeout=60) as http:
        for i, cat in enumerate(categories):
            if i > 0:
                await asyncio.sleep(delay_seconds)

            params: dict[str, str | int] = {
                "search_query": f"cat:{cat} AND submittedDate:[{start_str} TO {end_str}]",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": max_results,
            }
            try:
                resp = await http.get(_BASE_URL, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"  [warn] arXiv error for {cat}: {exc}")
                continue

            # _parse_feed keeps papers >= since; we use start_date as the floor
            cat_papers = client._parse_feed(resp.text, since=start_date)  # type: ignore[attr-defined]
            # Filter out papers submitted after end_date
            cat_papers = [p for p in cat_papers if p.published_at <= end_date]

            for p in cat_papers:
                papers.setdefault(p.arxiv_id, p)

            print(f"  {cat}: {len(cat_papers)} papers in range")

    return list(papers.values())


async def _run(
    start_date: datetime,
    end_date: datetime,
    categories: list[str],
) -> None:
    print(f"\n{'='*60}")
    print(f"Backfill: {start_date.date()} → {end_date.date()}")
    print(f"Categories: {', '.join(categories)}")
    print(f"{'='*60}\n")

    # ── Step 1: Fetch papers from arXiv ───────────────────────────────────
    print("[1/3] Fetching papers from arXiv…")
    papers = await _fetch_date_range(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        max_results=settings.arxiv_max_results_per_fetch,
        delay_seconds=settings.arxiv_fetch_delay_seconds,
    )
    print(f"      → {len(papers)} unique papers fetched\n")

    if not papers:
        print("No papers found. Exiting.")
        return

    # ── Step 2: Index keywords + write to DB ──────────────────────────────
    print("[2/3] Indexing keywords and writing to DB…")
    indexer = KeywordIndexer()
    kw_results = [indexer.extract_keywords(p) for p in papers]
    window_date = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        writer = TrendWriter(session)
        new_papers, skipped = await writer.write_papers(papers)
        kw_count = await writer.write_keywords(kw_results, window_date)
        await session.commit()

    print(f"      → {new_papers} new papers, {skipped} skipped, {kw_count} keyword rows\n")

    # ── Step 3: Semantic Scholar citations ────────────────────────────────
    print("[3/3] Fetching Semantic Scholar citations…")
    arxiv_ids = [p.arxiv_id for p in papers]
    papers_found = 0
    papers_not_found = 0
    citations_stored = 0

    fetched_at = datetime.now(UTC)

    async with SemanticScholarClient(
        api_key=settings.semantic_scholar_api_key,
        base_url=settings.semantic_scholar_base_url,
        delay_seconds=settings.semantic_scholar_fetch_delay_seconds,
    ) as ss_client:
        for arxiv_id in arxiv_ids:
            result = await ss_client.fetch_paper_data(arxiv_id)

            if result is None:
                papers_not_found += 1
                continue

            papers_found += 1

            citation_rows = [
                {
                    "source_arxiv_id": arxiv_id,
                    "cited_paper_id": ref.paper_id,
                    "citation_type": "citation",
                    "fetched_at": fetched_at,
                }
                for ref in result.citations
            ]
            reference_rows = [
                {
                    "source_arxiv_id": arxiv_id,
                    "cited_paper_id": ref.paper_id,
                    "citation_type": "reference",
                    "fetched_at": fetched_at,
                }
                for ref in result.references
            ]
            author_rows = [
                {
                    "paper_id": arxiv_id,
                    "author_id": a.author_id,
                    "author_name": a.author_name,
                    "fetched_at": fetched_at,
                }
                for a in result.authors
            ]

            async with AsyncSessionLocal() as session:
                for batch in _batched(citation_rows + reference_rows, _BATCH_SIZE):
                    await session.execute(
                        insert(PaperCitation)
                        .values(batch)
                        .on_conflict_do_nothing(
                            index_elements=["source_arxiv_id", "cited_paper_id", "citation_type"]
                        )
                    )
                for batch in _batched(author_rows, _BATCH_SIZE):
                    await session.execute(
                        insert(PaperAuthor)
                        .values(batch)
                        .on_conflict_do_nothing(index_elements=["paper_id", "author_id"])
                    )
                await session.commit()

            citations_stored += len(citation_rows) + len(reference_rows)

    print(f"      → {papers_found} found, {papers_not_found} not in S2, {citations_stored} citation rows\n")

    print("Done.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill historical arXiv data")
    parser.add_argument("--start-date", default="2024-10-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", default="2024-12-31", help="End date YYYY-MM-DD")
    parser.add_argument("--categories", default="cs.CL,cs.AI", help="Comma-separated arXiv categories")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=UTC)
    end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=UTC)
    cats = [c.strip() for c in args.categories.split(",")]

    asyncio.run(_run(start, end, cats))
