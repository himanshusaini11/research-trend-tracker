"""Semantic Scholar API client.

Fetches citation/reference edges and author records for arXiv papers.
Rate limit (anonymous): 100 req / 5 min  →  1 req / 3 s default delay.
Rate limit (with API key): 1000 req / 5 min.

Usage (batch — preferred):
    async with SemanticScholarClient(...) as client:
        for arxiv_id in ids:
            paper = await client.fetch_paper_data(arxiv_id)

Usage (single call / tests):
    client = SemanticScholarClient(...)
    paper = await client.fetch_paper_data(arxiv_id)  # creates a temporary client
"""
from __future__ import annotations

import asyncio
import random
from types import TracebackType

import httpx

from app.core.exceptions import IngestionError
from app.core.logger import get_logger
from app.ingestion.schemas import (
    SemanticScholarAuthor,
    SemanticScholarPaper,
    SemanticScholarPaperRef,
)

log = get_logger(__name__)

_FIELDS = "paperId,year,authors,citations,references"
_BACKOFF_BASE_SECONDS: float = 1.0
_BACKOFF_MAX_SECONDS: float = 60.0
_RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def _backoff_wait(attempt: int) -> float:
    """Exponential backoff with full jitter: uniform(0, min(base*2^attempt, max))."""
    ceiling = min(_BACKOFF_BASE_SECONDS * (2**attempt), _BACKOFF_MAX_SECONDS)
    return random.uniform(0, ceiling)  # noqa: S311 — not cryptographic


class SemanticScholarClient:
    """Async client for the Semantic Scholar Graph API.

    Args:
        api_key: Optional API key sent as ``x-api-key``. Raises the rate limit
                 from 100 req/5 min to 1000 req/5 min.
        base_url: Base URL of the Semantic Scholar Graph API.
        delay_seconds: Politeness delay between successive requests.
        max_retries: Maximum number of retry attempts on transient errors.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.semanticscholar.org/graph/v1",
        delay_seconds: float = 3.0,
        max_retries: int = 5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._delay_seconds = delay_seconds
        self._max_retries = max_retries
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["x-api-key"] = api_key
        # Set by __aenter__; None means use a temporary client per call
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Async context manager — reuses a single httpx.AsyncClient for
    # all fetch_paper_data calls made inside the `async with` block.
    # ------------------------------------------------------------------

    async def __aenter__(self) -> SemanticScholarClient:
        self._client = httpx.AsyncClient(headers=self._headers, timeout=30)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_paper_data(self, arxiv_id: str) -> SemanticScholarPaper | None:
        """Fetch citation/reference/author data for a single arXiv paper.

        Returns:
            Parsed ``SemanticScholarPaper`` on success.
            ``None`` when Semantic Scholar has no record for this arXiv ID (404).

        Raises:
            IngestionError: On non-retryable HTTP errors or exhausted retries.
        """
        url = f"{self._base_url}/paper/ArXiv:{arxiv_id}"
        params = {"fields": _FIELDS}

        if self._client is not None:
            # Reuse the shared client from the context manager
            response = await self._get_with_backoff(self._client, url, params, arxiv_id)
        else:
            # Fallback: create a temporary client (single-call / test usage)
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                response = await self._get_with_backoff(client, url, params, arxiv_id)

        if response is None:
            return None

        return self._parse_response(response, arxiv_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _get_with_backoff(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str],
        arxiv_id: str,
    ) -> httpx.Response | None:
        """GET with exponential backoff on 429 / 5xx. Returns None on 404."""
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                wait = _backoff_wait(attempt - 1)
                log.warning(
                    "semantic_scholar_retry",
                    arxiv_id=arxiv_id,
                    attempt=attempt,
                    wait_seconds=round(wait, 2),
                )
                await asyncio.sleep(wait)
            else:
                # Politeness delay before every request (including first)
                await asyncio.sleep(self._delay_seconds)

            try:
                resp = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt == self._max_retries:
                    raise IngestionError(
                        f"semantic_scholar request failed after {self._max_retries} retries",
                        detail=str(exc),
                    ) from exc
                continue

            if resp.status_code == 404:
                log.info("semantic_scholar_not_found", arxiv_id=arxiv_id)
                return None

            if resp.status_code not in _RETRYABLE_STATUSES:
                resp.raise_for_status()
                return resp

            # Retryable status — log and loop
            if attempt == self._max_retries:
                raise IngestionError(
                    f"semantic_scholar returned {resp.status_code} after "
                    f"{self._max_retries} retries",
                    detail=f"arxiv_id={arxiv_id}",
                )

        # Unreachable, satisfies mypy
        raise IngestionError("semantic_scholar retry loop exited unexpectedly")

    def _parse_response(
        self, resp: httpx.Response, arxiv_id: str
    ) -> SemanticScholarPaper:
        data: dict = resp.json()

        authors = [
            SemanticScholarAuthor(
                author_id=a.get("authorId") or "",
                author_name=a.get("name") or "",
            )
            for a in data.get("authors") or []
            if a.get("authorId")  # skip entries with no ID
        ]

        citations = [
            SemanticScholarPaperRef(paper_id=c["paperId"])
            for c in data.get("citations") or []
            if c.get("paperId")
        ]

        references = [
            SemanticScholarPaperRef(paper_id=r["paperId"])
            for r in data.get("references") or []
            if r.get("paperId")
        ]

        log.info(
            "semantic_scholar_fetched",
            arxiv_id=arxiv_id,
            semantic_scholar_id=data.get("paperId"),
            citations=len(citations),
            references=len(references),
            authors=len(authors),
        )

        return SemanticScholarPaper(
            semantic_scholar_id=data["paperId"],
            arxiv_id=arxiv_id,
            year=data.get("year"),
            authors=authors,
            citations=citations,
            references=references,
        )
