"""Anthropic Claude Haiku batch entity extractor.

Uses the Anthropic Messages Batch API to process all papers in a single
batch job. extract() falls back to the standard Messages API for one-off calls.
"""
from __future__ import annotations

import asyncio

import anthropic
from anthropic.types import TextBlock

from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.extractors.base import (
    BaseEntityExtractor,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.graph.schemas import EntityExtractionResult

log = get_logger(__name__)

# Anthropic Batch API limit: 100,000 requests per batch
_BATCH_CHUNK_SIZE = 10_000


class AnthropicHaikuExtractor(BaseEntityExtractor):
    """Entity extractor backed by a Claude model via the Anthropic Batch API.

    Args:
        api_key:       Anthropic API key.
        poll_interval: Seconds between batch status polls.
        model:         Claude model ID (override in subclasses).
        max_tokens:    Max output tokens per extraction.
    """

    _DEFAULT_MODEL = "claude-haiku-4-5-20251001"
    _DEFAULT_MAX_TOKENS = 256

    def __init__(self, api_key: str, poll_interval: int = 30) -> None:
        self._api_key = api_key
        self._poll_interval = poll_interval
        self._model = self._DEFAULT_MODEL
        self._max_tokens = self._DEFAULT_MAX_TOKENS

    def _client(self) -> anthropic.AsyncAnthropic:
        return anthropic.AsyncAnthropic(api_key=self._api_key)

    async def extract(self, paper: Paper) -> EntityExtractionResult:
        """Single-paper extraction using the standard Messages API (not batch)."""
        try:
            async with self._client() as client:
                msg = await client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": build_user_prompt(paper)}],
                )
            first = msg.content[0] if msg.content else None
            raw = first.text if isinstance(first, TextBlock) else "{}"
        except anthropic.APIError as exc:
            log.warning(
                "anthropic_extract_error",
                model=self._model,
                arxiv_id=paper.arxiv_id,
                error=str(exc),
            )
            return self._empty(paper.arxiv_id)

        return self._parse(paper.arxiv_id, raw)

    async def extract_batch(
        self,
        papers: list[Paper],
    ) -> dict[str, EntityExtractionResult]:
        """Submit all papers as Anthropic Batch API job(s), poll until done.

        Automatically splits into chunks of ≤10,000 (faster to complete and
        easier to retry than one giant batch).
        """
        all_results: dict[str, EntityExtractionResult] = {}
        for chunk_start in range(0, len(papers), _BATCH_CHUNK_SIZE):
            chunk = papers[chunk_start: chunk_start + _BATCH_CHUNK_SIZE]
            chunk_results = await self._run_batch(chunk)
            all_results.update(chunk_results)
        return all_results

    async def _run_batch(
        self, papers: list[Paper]
    ) -> dict[str, EntityExtractionResult]:
        """Submit one batch job and poll until complete."""
        requests = [
            {
                "custom_id": paper.arxiv_id,
                "params": {
                    "model": self._model,
                    "max_tokens": self._max_tokens,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": build_user_prompt(paper)}
                    ],
                },
            }
            for paper in papers
        ]

        async with self._client() as client:
            batch = await client.messages.batches.create(requests=requests)  # type: ignore[arg-type]
            batch_id: str = batch.id
            log.info(
                "anthropic_batch_submitted",
                model=self._model,
                batch_id=batch_id,
                papers=len(papers),
            )

            # Poll until processing_status == "ended"
            while True:
                status = await client.messages.batches.retrieve(batch_id)
                if status.processing_status == "ended":
                    break
                log.info(
                    "anthropic_batch_polling",
                    batch_id=batch_id,
                    status=status.processing_status,
                )
                await asyncio.sleep(self._poll_interval)

            # Collect results
            results: dict[str, EntityExtractionResult] = {}
            async for item in await client.messages.batches.results(batch_id):
                arxiv_id: str = item.custom_id
                if item.result.type == "succeeded":  # type: ignore[union-attr]
                    first_block = item.result.message.content[0]  # type: ignore[union-attr]
                    raw = first_block.text if isinstance(first_block, TextBlock) else "{}"
                    results[arxiv_id] = self._parse(arxiv_id, raw)
                else:
                    log.warning(
                        "anthropic_batch_item_failed",
                        arxiv_id=arxiv_id,
                        result_type=item.result.type,  # type: ignore[union-attr]
                    )
                    results[arxiv_id] = self._empty(arxiv_id)

        log.info("anthropic_batch_complete", batch_id=batch_id, results=len(results))
        return results
