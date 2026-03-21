"""Factory for creating entity extraction backends from a string identifier."""
from __future__ import annotations

from app.core.config import settings
from app.graph.extractors.base import BaseEntityExtractor


def get_extractor(backend: str) -> BaseEntityExtractor:
    """Return the appropriate extractor for the given backend name.

    Args:
        backend: One of "ollama", "anthropic-haiku", "anthropic-sonnet".

    Raises:
        ValueError: If the backend name is not recognised.
        RuntimeError: If required settings (e.g. ANTHROPIC_API_KEY) are missing.
    """
    if backend == "ollama":
        from app.graph.extractors.ollama import OllamaExtractor
        return OllamaExtractor(
            ollama_url=settings.ollama_url,
            model=settings.ollama_model,
            timeout=settings.ollama_request_timeout_seconds,
        )

    if backend in ("anthropic-haiku", "anthropic-sonnet"):
        if not settings.anthropic_api_key:
            raise RuntimeError(
                f"Backend '{backend}' requires ANTHROPIC_API_KEY to be set in .env"
            )
        if backend == "anthropic-haiku":
            from app.graph.extractors.anthropic_haiku import AnthropicHaikuExtractor
            return AnthropicHaikuExtractor(
                api_key=settings.anthropic_api_key,
                poll_interval=settings.anthropic_batch_poll_interval_seconds,
            )
        from app.graph.extractors.anthropic_sonnet import AnthropicSonnetExtractor
        return AnthropicSonnetExtractor(
            api_key=settings.anthropic_api_key,
            poll_interval=settings.anthropic_batch_poll_interval_seconds,
        )

    raise ValueError(
        f"Unknown extraction backend: '{backend}'. "
        "Valid options: ollama, anthropic-haiku, anthropic-sonnet"
    )
