"""Ollama-backed entity extractor.

Sends requests to the local Ollama /api/generate endpoint using JSON mode.
extract_batch() runs extractions concurrently via asyncio.gather + Semaphore.
"""
from __future__ import annotations

import asyncio

import httpx

from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.extractors.base import BaseEntityExtractor, build_user_prompt
from app.graph.schemas import EntityExtractionResult

log = get_logger(__name__)


class OllamaExtractor(BaseEntityExtractor):
    """Entity extractor backed by a local Ollama model.

    Args:
        ollama_url: Base URL of the Ollama API (e.g. http://localhost:11434).
        model:      Ollama model name (e.g. qwen3.5:27b).
        timeout:    HTTP request timeout in seconds.
    """

    def __init__(self, ollama_url: str, model: str, timeout: int) -> None:
        self._url = ollama_url.rstrip("/") + "/api/generate"
        self._model = model
        self._timeout = timeout

    async def extract(self, paper: Paper) -> EntityExtractionResult:
        """Call Ollama for a single paper. Returns empty result on any failure."""
        prompt = build_user_prompt(paper)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._url,
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "think": False,  # disable reasoning/thinking mode (qwen3, deepseek-r1, etc.)
                    },
                )
                resp.raise_for_status()
                raw_json: str = resp.json().get("response", "{}")
        except httpx.HTTPError as exc:
            log.warning(
                "ollama_extractor_http_error",
                arxiv_id=paper.arxiv_id,
                error=str(exc),
            )
            return self._empty(paper.arxiv_id)

        return self._parse(paper.arxiv_id, raw_json)

    async def extract_batch(
        self,
        papers: list[Paper],
        concurrency: int = 1,
    ) -> dict[str, EntityExtractionResult]:
        """Extract entities for multiple papers concurrently.

        Args:
            papers:      Papers to process.
            concurrency: Max simultaneous Ollama calls (default 1 = sequential).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def _one(paper: Paper) -> EntityExtractionResult:
            async with semaphore:
                return await self.extract(paper)

        results = await asyncio.gather(*[_one(p) for p in papers])
        return {r.arxiv_id: r for r in results}
