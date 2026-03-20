"""arxiv_ingestion DAG — fetch, index, and persist arXiv papers daily."""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, date, datetime, timedelta
from itertools import islice
from typing import Iterator

import structlog
from airflow import DAG
from airflow.operators.python import PythonOperator

log = structlog.get_logger(__name__)


def _on_failure(context: dict) -> None:
    log.error(
        "airflow_task_failed",
        dag_id=context["dag"].dag_id,
        task_id=context["task"].task_id,
        exception=str(context.get("exception")),
    )


default_args = {
    "owner": "airflow",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": _on_failure,
}


# ---------------------------------------------------------------------------
# Task 1 — fetch papers from arXiv
# ---------------------------------------------------------------------------
def fetch_papers(**context) -> None:  # type: ignore[type-arg]
    from app.core.config import settings
    from app.ingestion.arxiv_client import ArxivClient

    async def _run() -> list:
        client = ArxivClient(
            categories=settings.arxiv_categories,
            max_results=settings.arxiv_max_results_per_fetch,
            delay_seconds=settings.arxiv_fetch_delay_seconds,
        )
        return await client.fetch_recent(days_back=1)

    papers = asyncio.run(_run())
    paper_dicts = [p.model_dump(mode="json") for p in papers]
    context["ti"].xcom_push(key="papers", value=paper_dicts)
    log.info("fetch_papers_complete", count=len(papers))


# ---------------------------------------------------------------------------
# Task 2 — extract keywords
# ---------------------------------------------------------------------------
def index_keywords(**context) -> None:  # type: ignore[type-arg]
    from app.ingestion.keyword_indexer import KeywordIndexer
    from app.ingestion.schemas import ArxivPaper

    paper_dicts = context["ti"].xcom_pull(key="papers", task_ids="fetch_papers") or []
    papers = [ArxivPaper(**d) for d in paper_dicts]

    indexer = KeywordIndexer()
    results = [indexer.extract_keywords(p) for p in papers]

    context["ti"].xcom_push(
        key="keyword_results",
        value=[r.model_dump() for r in results],
    )
    log.info("index_keywords_complete", count=len(results))


# ---------------------------------------------------------------------------
# Task 3 — write to DB
# ---------------------------------------------------------------------------
def write_to_db(**context) -> None:  # type: ignore[type-arg]
    from app.core.database import AsyncSessionLocal
    from app.ingestion.schemas import ArxivPaper, IngestionResult, KeywordExtractionResult
    from app.ingestion.trend_writer import TrendWriter

    paper_dicts = context["ti"].xcom_pull(key="papers", task_ids="fetch_papers") or []
    result_dicts = context["ti"].xcom_pull(key="keyword_results", task_ids="index_keywords") or []

    papers = [ArxivPaper(**d) for d in paper_dicts]
    kw_results = [KeywordExtractionResult(**d) for d in result_dicts]
    window_date = date.today()
    t0 = time.monotonic()

    async def _run() -> tuple[int, int, int]:
        async with AsyncSessionLocal() as session:
            writer = TrendWriter(session)
            new, skipped = await writer.write_papers(papers)
            kw_count = await writer.write_keywords(kw_results, window_date)
            await session.commit()
        return new, skipped, kw_count

    new, skipped, kw_count = asyncio.run(_run())

    result = IngestionResult(
        papers_fetched=len(papers),
        papers_new=new,
        papers_skipped=skipped,
        keywords_indexed=kw_count,
        errors=[],
        duration_seconds=time.monotonic() - t0,
    )
    log.info("write_to_db_complete", **result.model_dump())


# ---------------------------------------------------------------------------
# Task 4 — fetch citation/author data from Semantic Scholar
# ---------------------------------------------------------------------------

def _dag_batched(lst: list, n: int) -> Iterator[list]:
    it = iter(lst)
    while chunk := list(islice(it, n)):
        yield chunk


def fetch_semantic_scholar(**context) -> None:  # type: ignore[type-arg]
    from sqlalchemy import update
    from sqlalchemy.dialects.postgresql import insert

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.models import Paper, PaperAuthor, PaperCitation
    from app.ingestion.semantic_scholar import SemanticScholarClient

    _BATCH_SIZE = 2_000

    paper_dicts = context["ti"].xcom_pull(key="papers", task_ids="fetch_papers") or []
    arxiv_ids: list[str] = [d["arxiv_id"] for d in paper_dicts]

    async def _run() -> tuple[int, int, int, int]:
        papers_found = 0
        papers_not_found = 0
        citations_stored = 0
        authors_stored = 0
        fetched_at = datetime.now(UTC)

        async with SemanticScholarClient(
            api_key=settings.semantic_scholar_api_key,
            base_url=settings.semantic_scholar_base_url,
            delay_seconds=settings.semantic_scholar_fetch_delay_seconds,
        ) as client:
            for arxiv_id in arxiv_ids:
                result = await client.fetch_paper_data(arxiv_id)

                if result is None:
                    papers_not_found += 1
                    continue

                papers_found += 1

                async with AsyncSessionLocal() as session:
                    # Update semantic_scholar_id on the canonical papers row
                    await session.execute(
                        update(Paper)
                        .where(Paper.arxiv_id == arxiv_id)
                        .values(semantic_scholar_id=result.semantic_scholar_id)
                    )

                    # Insert citation edges (ON CONFLICT DO NOTHING — idempotent)
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
                    for batch in _dag_batched(citation_rows + reference_rows, _BATCH_SIZE):
                        await session.execute(
                            insert(PaperCitation)
                            .values(batch)
                            .on_conflict_do_nothing(
                                index_elements=["source_arxiv_id", "cited_paper_id", "citation_type"]
                            )
                        )
                    citations_stored += len(citation_rows) + len(reference_rows)

                    # Insert author records (ON CONFLICT DO NOTHING — idempotent)
                    author_rows = [
                        {
                            "paper_id": arxiv_id,
                            "author_id": a.author_id,
                            "author_name": a.author_name,
                            "fetched_at": fetched_at,
                        }
                        for a in result.authors
                    ]
                    for batch in _dag_batched(author_rows, _BATCH_SIZE):
                        await session.execute(
                            insert(PaperAuthor)
                            .values(batch)
                            .on_conflict_do_nothing(
                                index_elements=["paper_id", "author_id"]
                            )
                        )
                    authors_stored += len(author_rows)

                    await session.commit()

        return papers_found, papers_not_found, citations_stored, authors_stored

    papers_found, papers_not_found, citations_stored, authors_stored = asyncio.run(_run())
    log.info(
        "fetch_semantic_scholar_complete",
        papers_found=papers_found,
        papers_not_found=papers_not_found,
        citations_stored=citations_stored,
        authors_stored=authors_stored,
    )


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="arxiv_ingestion",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion"],
    description="Fetch arXiv papers, extract keywords, write to Postgres",
) as dag:
    t_fetch = PythonOperator(task_id="fetch_papers", python_callable=fetch_papers)
    t_index = PythonOperator(task_id="index_keywords", python_callable=index_keywords)
    t_write = PythonOperator(task_id="write_to_db", python_callable=write_to_db)
    t_semantic = PythonOperator(
        task_id="fetch_semantic_scholar", python_callable=fetch_semantic_scholar
    )

    t_fetch >> t_index >> t_write >> t_semantic
