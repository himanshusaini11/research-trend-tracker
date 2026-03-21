"""Run the full graph + analysis + prediction pipeline manually (outside Airflow).

Processes all papers in the DB through:
  1. EntityExtractor   — extract concepts/methods via Ollama
  2. RelationBuilder   — write nodes/edges to AGE
  3. GraphAnalyzer     — compute bridge-node centrality + velocity
  4. PredictionSynthesizer — generate structured prediction report
  5. ReportArchive     — persist report to prediction_reports table

Prints the full report to stdout and the report UUID for later validation.

Usage:
    uv run python scripts/run_graph_pipeline.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.graph.entity_extractor import EntityExtractor
from app.graph.graph_analyzer import GraphAnalyzer
from app.graph.prediction_synthesizer import PredictionSynthesizer
from app.graph.report_archive import ReportArchive
from app.graph.relation_builder import RelationBuilder

_TOPIC_CONTEXT = "LLM/AI research Oct-Dec 2024"


async def _run(
    skip_extraction: bool = False,
    skip_graph: bool = False,
    skip_analysis: bool = False,
    skip_prediction: bool = False,
) -> None:
    print(f"\n{'='*60}")
    print("Graph + Prediction Pipeline")
    print(f"Topic context: {_TOPIC_CONTEXT}")
    print(f"{'='*60}\n")

    # ── Step 1 & 2: Entity extraction + graph building ────────────────────
    if skip_extraction:
        print("[1/4] Skipped (--skip-extraction)")
        papers_processed = total_concepts = total_edges = 0
    else:
        print("[1/4] Running EntityExtractor + RelationBuilder…")

        extractor = EntityExtractor(
            ollama_url=settings.ollama_url,
            model=settings.ollama_model,
            timeout=settings.ollama_request_timeout_seconds,
        )

        async with AsyncSessionLocal() as session:
            paper_rows = await extractor.get_unprocessed_papers(session)

        papers_processed = 0
        total_concepts = 0
        total_edges = 0

        async with AsyncSessionLocal() as session:
            builder = RelationBuilder(session)
            await builder.setup()

            for paper in paper_rows:
                # Load authors for this paper from DB
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

                result = await extractor.extract(paper.arxiv_id, paper.title, paper.abstract)

                concepts_created, edges_created = await builder.build_for_paper(
                    arxiv_id=paper.arxiv_id,
                    title=paper.title,
                    year=year,
                    authors=authors,
                    result=result,
                )

                if not skip_graph:
                    await builder.build_concept_cooccurrence(paper.arxiv_id)

                await extractor.mark_processed(session, paper)

                papers_processed += 1
                total_concepts += concepts_created
                total_edges += edges_created

            await session.commit()

    print(f"      → {papers_processed} papers, {total_concepts} concepts, {total_edges} edges\n")

    # ── Step 2: Graph analysis (bridge nodes + velocity) ──────────────────
    signals: list = []
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
                        help="Skip Ollama entity extraction + relation building")
    parser.add_argument("--skip-graph", action="store_true",
                        help="Skip CO_OCCURS_WITH edge building")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="Skip BridgeNodeDetector + VelocityTracker")
    parser.add_argument("--skip-prediction", action="store_true",
                        help="Skip PredictionSynthesizer + ReportArchive")
    args = parser.parse_args()
    asyncio.run(_run(
        skip_extraction=args.skip_extraction,
        skip_graph=args.skip_graph,
        skip_analysis=args.skip_analysis,
        skip_prediction=args.skip_prediction,
    ))
