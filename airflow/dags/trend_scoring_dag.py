"""trend_scoring DAG — compute and persist trend scores daily."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import structlog
from airflow import DAG
from airflow.operators.python import PythonOperator

log = structlog.get_logger(__name__)

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def score_trends(**context) -> None:  # type: ignore[type-arg]
    from app.analytics.trend_scorer import TrendScorer
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal

    window_date = date.today()

    async def _run() -> dict[str, int]:
        results: dict[str, int] = {}
        for category in settings.arxiv_categories:
            async with AsyncSessionLocal() as session:
                scorer = TrendScorer(session)
                count = await scorer.score_and_persist(category, window_date)
                await session.commit()
            results[category] = count
            log.info("category_scored", category=category, scores_written=count)
        return results

    results = asyncio.run(_run())
    log.info("score_trends_complete", results=results)


with DAG(
    dag_id="trend_scoring",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["analytics"],
    description="Compute and persist trend scores for all tracked arXiv categories",
) as dag:
    PythonOperator(task_id="score_trends", python_callable=score_trends)
