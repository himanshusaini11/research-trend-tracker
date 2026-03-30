from __future__ import annotations

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import EmbeddingError

log = structlog.get_logger(__name__)


async def get_embedding(text: str) -> list[float]:
    """Return a single embedding vector for text."""
    url = f"{settings.ollama_url}/api/embed"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client:
            resp = await client.post(
                url, json={"model": settings.embed_model, "input": text}
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]
    except Exception as exc:
        log.error("embedding_failed", text_snippet=text[:100], error=str(exc))
        raise EmbeddingError(f"Failed to embed text: {exc}") from exc


async def get_embeddings_batch(texts: list[str]) -> list[float | None]:
    """Return embeddings for a batch of texts. Returns None for any failed item."""
    results: list[float | None] = []
    url = f"{settings.ollama_url}/api/embed"
    async with httpx.AsyncClient(timeout=settings.ollama_request_timeout_seconds) as client:
        for text in texts:
            try:
                resp = await client.post(
                    url, json={"model": settings.embed_model, "input": text}
                )
                resp.raise_for_status()
                results.append(resp.json()["embeddings"][0])
            except Exception as exc:
                log.error(
                    "batch_embedding_item_failed",
                    text_snippet=text[:100],
                    error=str(exc),
                    batch_size=len(texts),
                )
                results.append(None)
    return results
