"""Anthropic Claude Haiku batch entity extractor.

Uses the Anthropic Messages Batch API to process all papers in a single
batch job. extract() falls back to the standard Messages API for one-off calls.
"""
from __future__ import annotations

import asyncio

import anthropic
from anthropic import AsyncAnthropic
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
# Max concurrent batch jobs in flight (Anthropic concurrent-batch limit)
_SUBMIT_CONCURRENCY = 5


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

        Submits chunks sequentially (large payloads — avoid overwhelming the
        connection) then polls all batch jobs in parallel once all are submitted.
        """
        chunks = [
            papers[i: i + _BATCH_CHUNK_SIZE]
            for i in range(0, len(papers), _BATCH_CHUNK_SIZE)
        ]

        all_results: dict[str, EntityExtractionResult] = {}
        total_chunks = len(chunks)

        async with self._client() as client:
            # Process in groups of _SUBMIT_CONCURRENCY to stay within Anthropic's
            # concurrent-batch limit. Within each group: submit sequentially
            # (large payloads), then poll in parallel.
            for group_start in range(0, total_chunks, _SUBMIT_CONCURRENCY):
                group = chunks[group_start: group_start + _SUBMIT_CONCURRENCY]

                batch_infos: list[tuple[str, dict[str, str]]] = []
                for chunk in group:
                    chunk_num = group_start + len(batch_infos) + 1
                    id_map = {self._sanitize_id(p.arxiv_id): p.arxiv_id for p in chunk}
                    requests = [
                        {
                            "custom_id": self._sanitize_id(paper.arxiv_id),
                            "params": {
                                "model": self._model,
                                "max_tokens": self._max_tokens,
                                "system": SYSTEM_PROMPT,
                                "messages": [
                                    {"role": "user", "content": build_user_prompt(paper)}
                                ],
                            },
                        }
                        for paper in chunk
                    ]
                    batch = await client.messages.batches.create(requests=requests)  # type: ignore[arg-type]
                    batch_infos.append((batch.id, id_map))
                    log.info(
                        "anthropic_batch_submitted",
                        model=self._model,
                        batch_id=batch.id,
                        chunk=chunk_num,
                        total_chunks=total_chunks,
                        papers=len(chunk),
                    )

                # Wait for this group to fully complete before submitting next group
                results_list = await asyncio.gather(
                    *[
                        self._poll_batch(client, batch_id, id_map)
                        for batch_id, id_map in batch_infos
                    ]
                )
                for r in results_list:
                    all_results.update(r)
                log.info(
                    "anthropic_batch_group_complete",
                    group_start=group_start + 1,
                    group_end=group_start + len(group),
                    total_results=len(all_results),
                )

        return all_results

    @staticmethod
    def _sanitize_id(arxiv_id: str) -> str:
        """Map arXiv ID to a custom_id safe for Anthropic Batch API.

        Anthropic requires custom_id matching ^[a-zA-Z0-9_-]{1,64}$.
        arXiv IDs contain '.' (e.g. 2202.00146) and old-style IDs contain '/'.
        Replace both with '_'.
        """
        return arxiv_id.replace(".", "_").replace("/", "_")[:64]

    async def _poll_batch(
        self,
        client: AsyncAnthropic,
        batch_id: str,
        id_map: dict[str, str],
    ) -> dict[str, EntityExtractionResult]:
        """Poll one batch job until complete, then collect and return results."""
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

        results: dict[str, EntityExtractionResult] = {}
        async for item in await client.messages.batches.results(batch_id):
            sanitized: str = item.custom_id
            arxiv_id = id_map.get(sanitized, sanitized)
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
