"""Entity extractor — calls Ollama and parses structured JSON from paper text.

Uses Ollama's native JSON mode (format="json") to constrain output.
Must NOT import from app/api/ or app/mcp_server/.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.schemas import EntityExtractionResult

log = get_logger(__name__)

_PROMPT_TEMPLATE = """\
Extract named entities from the research paper below.

Respond with ONLY valid JSON — no prose, no markdown fences, nothing else.
Use exactly this structure:
{{"concepts": ["..."], "methods": ["..."], "datasets": ["..."]}}

- concepts: key research topics or ideas (e.g. "attention mechanism", "knowledge graph")
- methods: algorithms or techniques used (e.g. "BERT", "gradient descent")
- datasets: datasets referenced (e.g. "ImageNet", "SQuAD"); empty list if none

Title: {title}
Abstract: {abstract}"""


class EntityExtractor:
    """Async Ollama client that extracts entities from paper abstracts.

    Args:
        ollama_url: Base URL of the Ollama API (e.g. http://localhost:11434).
        model: Ollama model name (e.g. llama3.2).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, ollama_url: str, model: str, timeout: int) -> None:
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def get_unprocessed_papers(self, session: AsyncSession) -> list[Paper]:
        """Return papers where graph_processed_at IS NULL (not yet entity-extracted)."""
        rows = await session.execute(
            select(Paper).where(Paper.graph_processed_at.is_(None))
        )
        return list(rows.scalars().all())

    async def mark_processed(self, session: AsyncSession, paper: Paper) -> None:
        """Stamp graph_processed_at on the paper and flush (caller commits)."""
        paper.graph_processed_at = datetime.now(UTC)
        await session.flush()

    async def extract(
        self,
        arxiv_id: str,
        title: str,
        abstract: str,
    ) -> EntityExtractionResult:
        """Run entity extraction for a single paper.

        Returns an ``EntityExtractionResult`` with empty lists on any failure
        (malformed JSON, connection error, etc.) so callers can proceed without
        crashing the pipeline.
        """
        prompt = _PROMPT_TEMPLATE.format(title=title, abstract=abstract)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                raw_json: str = resp.json().get("response", "{}")
        except httpx.HTTPError as exc:
            log.warning(
                "entity_extractor_http_error",
                arxiv_id=arxiv_id,
                error=str(exc),
            )
            return EntityExtractionResult(arxiv_id=arxiv_id, concepts=[], methods=[], datasets=[])

        return self._parse(arxiv_id, raw_json)

    def _parse(self, arxiv_id: str, raw_json: str) -> EntityExtractionResult:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            log.warning(
                "entity_extractor_malformed_json",
                arxiv_id=arxiv_id,
                raw=raw_json[:200],
            )
            return EntityExtractionResult(arxiv_id=arxiv_id, concepts=[], methods=[], datasets=[])

        return EntityExtractionResult(
            arxiv_id=arxiv_id,
            concepts=_coerce_list(data.get("concepts")),
            methods=_coerce_list(data.get("methods")),
            datasets=_coerce_list(data.get("datasets")),
        )


def _coerce_list(value: object) -> list[str]:
    """Accept a list of strings, or return [] for any other type."""
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return []
