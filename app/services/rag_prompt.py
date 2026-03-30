from __future__ import annotations

from app.services.rag import PaperResult


def build_prediction_prompt(prediction_text: str, sources: list[PaperResult]) -> str:
    context_blocks = "\n".join(
        f"[{i + 1}] {src.title} ({src.published_at.date()}) — {src.abstract_snippet}"
        for i, src in enumerate(sources)
    )
    return (
        "You are a research trend analyst. Use the numbered sources below to support your "
        "analysis. Cite sources as [1], [2], etc.\n\n"
        f"Sources:\n{context_blocks}\n\n"
        f"Prediction to analyse:\n{prediction_text}"
    )


def build_search_summary_prompt(query: str, sources: list[PaperResult]) -> str:
    context_blocks = "\n".join(
        f"[{i + 1}] {src.title} ({src.published_at.date()}) — {src.abstract_snippet}"
        for i, src in enumerate(sources)
    )
    return (
        "You are a research assistant. Summarize what the literature says about the query "
        "below. Cite sources as [1], [2], etc.\n\n"
        f"Sources:\n{context_blocks}\n\n"
        f"Query: {query}"
    )
