"""Base class and shared utilities for all entity extraction backends."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from app.core.logger import get_logger
from app.core.models import Paper
from app.graph.schemas import EntityExtractionResult

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Canonical extraction prompt (shared across all backends)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a research paper analyzer. Extract key concepts, methods, and datasets. "
    "Always respond with valid JSON only. No prose, no markdown."
)

_USER_TEMPLATE = """\
Extract from this paper:
Title: {title}
Abstract: {abstract}

Respond ONLY with this JSON (no other text):
{{
  "concepts": ["Concept One", "Concept Two"],
  "methods": ["Method One"],
  "datasets": ["Dataset One"]
}}

Rules:
- Title Case for all items
- Max: 8 concepts, 5 methods, 3 datasets
- Only explicitly mentioned items
- Empty list [] if none found"""


def build_user_prompt(paper: Paper) -> str:
    return _USER_TEMPLATE.format(
        title=paper.title,
        abstract=paper.abstract[:800],
    )


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseEntityExtractor(ABC):
    """ABC for LLM entity extraction backends."""

    @abstractmethod
    async def extract(self, paper: Paper) -> EntityExtractionResult:
        """Extract entities from a single paper."""
        ...

    @abstractmethod
    async def extract_batch(
        self, papers: list[Paper]
    ) -> dict[str, EntityExtractionResult]:
        """Extract entities from multiple papers efficiently.

        Returns a mapping of arxiv_id → EntityExtractionResult.
        For Ollama this uses asyncio.gather; for Anthropic it uses the Batch API.
        """
        ...

    # ------------------------------------------------------------------
    # Shared JSON parsing logic
    # ------------------------------------------------------------------

    def _parse(self, arxiv_id: str, raw_json: str) -> EntityExtractionResult:
        """Parse a raw JSON string from any backend into EntityExtractionResult.

        Handles:
        - Markdown-fenced responses (```json ... ```)
        - Empty strings
        - Valid JSON with missing keys (returns [] for each)
        """
        text = raw_json.strip()

        # Strip <think>...</think> blocks (qwen3, deepseek-r1 reasoning models)
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

        # Strip markdown fences if the model wrapped the JSON
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        if not text:
            return self._empty(arxiv_id)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning(
                "entity_extractor_malformed_json",
                arxiv_id=arxiv_id,
                raw=raw_json[:200],
            )
            return self._empty(arxiv_id)

        return EntityExtractionResult(
            arxiv_id=arxiv_id,
            concepts=_coerce_list(data.get("concepts")),
            methods=_coerce_list(data.get("methods")),
            datasets=_coerce_list(data.get("datasets")),
        )

    def _empty(self, arxiv_id: str) -> EntityExtractionResult:
        return EntityExtractionResult(arxiv_id=arxiv_id, concepts=[], methods=[], datasets=[])


def _coerce_list(value: object) -> list[str]:
    if isinstance(value, list):
        # Strip surrogate characters — asyncpg rejects them as invalid UTF-8
        return [str(v).encode("utf-8", "ignore").decode("utf-8") for v in value if v]
    return []
