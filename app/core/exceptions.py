from __future__ import annotations


class AppError(Exception):
    """Base class for all application exceptions."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, detail={self.detail!r})"


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""


class ValidationError(AppError):
    """Raised when input data fails business-level validation."""


class AuthenticationError(AppError):
    """Raised when a request cannot be authenticated (bad token / missing key)."""


class RateLimitExceededError(AppError):
    """Raised when a client exceeds the configured rate limit."""


class DatabaseError(AppError):
    """Raised when a database operation fails unexpectedly."""


class CacheError(AppError):
    """Raised when a Redis cache operation fails."""


class IngestionError(AppError):
    """Raised when the arXiv ingestion pipeline encounters an unrecoverable error."""


class LLMError(AppError):
    """Raised when the LLM (Ollama) call fails or returns an invalid response."""
