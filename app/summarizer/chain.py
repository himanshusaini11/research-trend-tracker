from __future__ import annotations

from datetime import UTC, datetime

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.core.exceptions import LLMError
from app.core.logger import get_logger
from app.summarizer.prompts import TREND_SUMMARY_HUMAN, TREND_SUMMARY_SYSTEM
from app.summarizer.schemas import TrendSummaryOutput

log = get_logger(__name__)


class TrendSummarizerChain:
    def __init__(self, ollama_url: str, model: str, timeout: int) -> None:
        self._model = model
        self._llm = ChatOllama(
            base_url=ollama_url,
            model=model,
            # timeout kwarg not supported in installed langchain-ollama version
        )
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", TREND_SUMMARY_SYSTEM),
                ("human", TREND_SUMMARY_HUMAN),
            ]
        )
        self._chain = self._prompt | self._llm

    async def summarize(
        self,
        category: str,
        window_days: int,
        keywords: list[str],
    ) -> TrendSummaryOutput:
        keywords_str = ", ".join(keywords)
        log.info(
            "summarizer_request",
            category=category,
            window_days=window_days,
            keyword_count=len(keywords),
            model=self._model,
        )

        try:
            response = await self._chain.ainvoke(
                {
                    "category": category,
                    "window_days": window_days,
                    "keywords": keywords_str,
                }
            )
        except httpx.ConnectError as exc:
            raise LLMError(
                "Cannot connect to Ollama at the configured URL",
                detail=str(exc),
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(
                "Ollama request timed out",
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise LLMError(
                "Unexpected error from LLM",
                detail=str(exc),
            ) from exc

        summary_text: str = response.content  # type: ignore[assignment]
        log.info(
            "summarizer_response",
            category=category,
            summary_length=len(summary_text),
            model=self._model,
        )

        return TrendSummaryOutput(
            category=category,
            window_days=window_days,
            summary=summary_text.strip(),
            keywords_covered=keywords,
            generated_at=datetime.now(UTC),
            model_used=self._model,
        )
