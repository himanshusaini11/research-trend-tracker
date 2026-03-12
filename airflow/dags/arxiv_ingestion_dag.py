"""arxiv_ingestion DAG — fetch, index, and persist arXiv papers daily."""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta

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

    t_fetch >> t_index >> t_write
