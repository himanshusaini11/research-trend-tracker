"""Run the full graph + analysis + prediction pipeline manually (outside Airflow).

Processes all (or --limit N) unprocessed papers through:
  1. Entity extraction  — via selected LLM backend (Ollama or Anthropic Batch)
  2. RelationBuilder    — write nodes/edges to AGE
  3. GraphAnalyzer      — compute bridge-node centrality + velocity
  4. PredictionSynthesizer — generate structured prediction report
  5. ReportArchive      — persist report to prediction_reports table

Usage (Ollama, 4 concurrent):
    uv run python scripts/run_graph_pipeline.py --concurrency 4

Usage (Anthropic Haiku batch):
    uv run python scripts/run_graph_pipeline.py --backend anthropic-haiku

Usage (benchmark, skip everything except extraction):
    uv run python scripts/run_graph_pipeline.py --limit 10 --skip-graph \\
        --skip-analysis --skip-prediction
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, text, update

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.models import Paper
from app.graph.extractors.factory import get_extractor
from app.graph.graph_analyzer import GraphAnalyzer
from app.graph.prediction_synthesizer import PredictionSynthesizer
from app.graph.report_archive import ReportArchive
from app.graph.relation_builder import RelationBuilder
from app.graph.schemas import EntityExtractionResult

_TOPIC_CONTEXT = "LLM/AI research Oct-Dec 2024"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _get_unprocessed_papers(limit: int | None) -> list[Paper]:
    """Load papers where graph_processed_at IS NULL, optionally capped at limit."""
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Paper).where(Paper.graph_processed_at.is_(None))
            )
        ).scalars().all()
    papers = list(rows)
    if limit is not None:
        papers = papers[:limit]
    return papers


async def _mark_processed(session, arxiv_id: str) -> None:  # type: ignore[no-untyped-def]
    """Stamp graph_processed_at via a direct UPDATE (session-safe across contexts)."""
    await session.execute(
        update(Paper)
        .where(Paper.arxiv_id == arxiv_id)
        .values(graph_processed_at=datetime.now(UTC))
    )


async def _build_and_mark(
    paper: Paper,
    result: EntityExtractionResult,
    skip_graph: bool,
) -> tuple[int, int]:
    """Write graph nodes/edges for one paper and stamp graph_processed_at.

    Each call opens its own session so concurrent callers don't share state.
    """
    async with AsyncSessionLocal() as session:
        builder = RelationBuilder(session)
        await builder.setup()

        # Author rows
        author_rows = (
            await session.execute(
                text(
                    "SELECT author_id, author_name FROM paper_authors"
                    " WHERE paper_id = :arxiv_id"
                ).bindparams(arxiv_id=paper.arxiv_id)
            )
        ).all()
        authors: list[tuple[str, str]] = [(r[0], r[1]) for r in author_rows]

        year: int | None = None
        try:
            year = paper.published_at.year
        except Exception:
            pass

        concepts_created, edges_created = await builder.build_for_paper(
            arxiv_id=paper.arxiv_id,
            title=paper.title,
            year=year,
            authors=authors,
            result=result,
        )

        if not skip_graph:
            await builder.build_concept_cooccurrence(paper.arxiv_id)

        await _mark_processed(session, paper.arxiv_id)
        await session.commit()

    return concepts_created, edges_created


# ---------------------------------------------------------------------------
# Extraction loops
# ---------------------------------------------------------------------------

async def _run_ollama_concurrent(
    paper_rows: list[Paper],
    skip_graph: bool,
    concurrency: int,
) -> tuple[int, int, int]:
    """Process papers concurrently with asyncio.gather + Semaphore.

    Returns (papers_processed, total_concepts, total_edges).
    """
    extractor = get_extractor("ollama")
    semaphore = asyncio.Semaphore(concurrency)

    papers_done = 0
    total_concepts = 0
    total_edges = 0
    total = len(paper_rows)
    start_t = time.monotonic()

    async def process_one(paper: Paper) -> None:
        nonlocal papers_done, total_concepts, total_edges

        async with semaphore:
            result = await extractor.extract(paper)
            c, e = await _build_and_mark(paper, result, skip_graph)

        # Update counters (safe: async is single-threaded, no await between reads)
        papers_done += 1
        total_concepts += c
        total_edges += e

        if papers_done % 500 == 0 or papers_done == total:
            elapsed = time.monotonic() - start_t
            rate = papers_done / elapsed
            remaining_min = (total - papers_done) / rate / 60 if rate > 0 else 0
            pct = papers_done / total * 100
            print(
                f"  [{papers_done:,} / {total:,}] processed ({pct:.1f}%) — "
                f"{elapsed/60:.1f} min elapsed, ~{remaining_min:.0f} min remaining"
            )

    await asyncio.gather(*[process_one(p) for p in paper_rows])
    return papers_done, total_concepts, total_edges


async def _run_anthropic_batch(
    paper_rows: list[Paper],
    backend: str,
    skip_graph: bool,
) -> tuple[int, int, int]:
    """Submit all papers to Anthropic Batch API, then write results to the graph.

    Returns (papers_processed, total_concepts, total_edges).
    """
    extractor = get_extractor(backend)
    print(f"  Submitting {len(paper_rows):,} papers to Anthropic Batch API…")
    results_map = await extractor.extract_batch(paper_rows)

    papers_done = 0
    total_concepts = 0
    total_edges = 0
    total = len(paper_rows)

    for paper in paper_rows:
        result = results_map.get(
            paper.arxiv_id,
            EntityExtractionResult(arxiv_id=paper.arxiv_id, concepts=[], methods=[], datasets=[]),
        )
        c, e = await _build_and_mark(paper, result, skip_graph)
        papers_done += 1
        total_concepts += c
        total_edges += e

        if papers_done % 500 == 0 or papers_done == total:
            print(f"  [{papers_done:,} / {total:,}] graph writes complete")

    return papers_done, total_concepts, total_edges


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def _run(
    skip_extraction: bool = False,
    skip_graph: bool = False,
    skip_analysis: bool = False,
    skip_prediction: bool = False,
    limit: int | None = None,
    concurrency: int = 1,
    backend: str = "ollama",
) -> None:
    print(f"\n{'='*60}")
    print("Graph + Prediction Pipeline")
    print(f"Topic context: {_TOPIC_CONTEXT}")
    print(f"Backend: {backend}  |  Concurrency: {concurrency}")
    print(f"{'='*60}\n")

    # ── Step 1: Entity extraction + graph building ─────────────────────────
    signals: list = []

    if skip_extraction:
        print("[1/4] Skipped (--skip-extraction)")
        papers_processed = total_concepts = total_edges = 0
    else:
        print("[1/4] Running entity extraction + RelationBuilder…")

        paper_rows = await _get_unprocessed_papers(limit)

        if not paper_rows:
            print("      → No unprocessed papers found. Exiting.")
            return

        print(f"      → {len(paper_rows):,} unprocessed papers queued\n")

        is_anthropic = backend in ("anthropic-haiku", "anthropic-sonnet")

        if is_anthropic:
            papers_processed, total_concepts, total_edges = await _run_anthropic_batch(
                paper_rows, backend, skip_graph
            )
        else:
            papers_processed, total_concepts, total_edges = await _run_ollama_concurrent(
                paper_rows, skip_graph, concurrency
            )

    print(f"\n      → {papers_processed} papers, {total_concepts} concepts, {total_edges} edges\n")

    # ── Step 2: Graph analysis (bridge nodes + velocity) ──────────────────
    if skip_analysis:
        print("[2/4] Skipped (--skip-analysis)")
    else:
        print("[2/4] Running GraphAnalyzer…")

        analyzer = GraphAnalyzer(
            top_n=settings.graph_top_n_concepts,
            k_samples=settings.graph_centrality_k_samples,
        )

        async with AsyncSessionLocal() as session:
            signals = await analyzer.analyze(session)
            await session.commit()

        print(f"      → {len(signals)} concept signals computed")
        if signals:
            print("      Top 5 concepts by composite score:")
            for s in signals[:5]:
                print(
                    f"        {s.concept_name:<30} "
                    f"composite={s.composite_score:.3f}  "
                    f"trend={s.trend}"
                )
        print()

    # ── Step 3: Prediction synthesis ──────────────────────────────────────
    if skip_prediction:
        print("[3/4] Skipped (--skip-prediction)")
        print("[4/4] Skipped (--skip-prediction)")
        return

    print("[3/4] Running PredictionSynthesizer (this may take a minute)…")

    synthesizer = PredictionSynthesizer(
        ollama_url=settings.ollama_url,
        model=settings.ollama_model,
        timeout=settings.ollama_request_timeout_seconds,
    )
    report = await synthesizer.synthesize(signals, topic_context=_TOPIC_CONTEXT)
    print(f"      → confidence: {report.overall_confidence}\n")

    # ── Step 4: Save report ───────────────────────────────────────────────
    print("[4/4] Saving report to ReportArchive…")

    archive = ReportArchive()
    async with AsyncSessionLocal() as session:
        report_id = await archive.save(
            session=session,
            topic_context=_TOPIC_CONTEXT,
            signals=signals,
            report=report,
            model_name=settings.ollama_model,
        )
        await session.commit()

    print(f"      → Report ID: {report_id}\n")

    # ── Print full report ─────────────────────────────────────────────────
    print(f"{'='*60}")
    print("PREDICTION REPORT")
    print(f"Topic: {_TOPIC_CONTEXT}")
    print(f"Overall confidence: {report.overall_confidence.upper()}")
    print(f"Time horizon: {report.time_horizon_months} months")
    print(f"Generated at: {datetime.now(UTC).isoformat()}")
    print(f"{'='*60}\n")

    print("EMERGING DIRECTIONS")
    print("-" * 40)
    for i, d in enumerate(report.emerging_directions, 1):
        print(f"  {i}. {d.direction}")
        print(f"     Confidence: {d.confidence}")
        print(f"     {d.reasoning}")
        print()

    print("UNEXPLORED GAPS")
    print("-" * 40)
    for i, g in enumerate(report.underexplored_gaps, 1):
        print(f"  {i}. {g.gap}")
        print(f"     {g.reasoning}")
        print()

    print("PREDICTED CONVERGENCES")
    print("-" * 40)
    for i, c in enumerate(report.predicted_convergences, 1):
        print(f"  {i}. {c.concept_a}  ↔  {c.concept_b}")
        print(f"     {c.reasoning}")
        print()

    print(f"{'='*60}")
    print(f"Report UUID: {report_id}")
    print(f"{'='*60}")
    print("\nTo validate this report:")
    print(
        f"  uv run python scripts/validate_prediction.py \\\n"
        f'    --report-id {report_id} \\\n'
        f'    --notes "your notes here" \\\n'
        f'    --accurate yes'
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the graph + prediction pipeline")
    parser.add_argument("--skip-extraction", action="store_true",
                        help="Skip entity extraction + relation building")
    parser.add_argument("--skip-graph", action="store_true",
                        help="Skip CO_OCCURS_WITH edge building")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="Skip BridgeNodeDetector + VelocityTracker")
    parser.add_argument("--skip-prediction", action="store_true",
                        help="Skip PredictionSynthesizer + ReportArchive")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N unprocessed papers (for benchmarking)")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Concurrent Ollama calls (default: 1). Ignored for Anthropic backends.")
    parser.add_argument("--backend", type=str, default=None,
                        help="LLM backend override: ollama | anthropic-haiku | anthropic-sonnet "
                             "(default: EXTRACTION_BACKEND from config)")
    args = parser.parse_args()

    effective_backend = args.backend or settings.extraction_backend

    asyncio.run(_run(
        skip_extraction=args.skip_extraction,
        skip_graph=args.skip_graph,
        skip_analysis=args.skip_analysis,
        skip_prediction=args.skip_prediction,
        limit=args.limit,
        concurrency=args.concurrency,
        backend=effective_backend,
    ))
