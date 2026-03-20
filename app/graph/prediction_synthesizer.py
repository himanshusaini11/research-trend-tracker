"""Prediction synthesizer — prompts Ollama to produce a structured prediction
report from ConceptSignal data.

The LLM's job is synthesis and prose ONLY. Analysis is already done by Week 3.
Uses direct httpx calls to Ollama /api/generate (NOT LangChain).
"""
from __future__ import annotations

import json

import httpx

from app.core.config import settings
from app.core.logger import get_logger
from app.graph.schemas import (
    ConceptSignal,
    EmergingDirection,
    PredictedConvergence,
    PredictionReport,
    UnexploredGap,
)

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a research trend analyst. You will be given quantitative signals about "
    "research concepts. Your job is to synthesize these signals into a structured "
    "prediction report. Respond ONLY in valid JSON. No prose, no markdown, no "
    "explanation outside the JSON."
)

_USER_PROMPT_TEMPLATE = """\
Based on these quantitative research signals for the past 30 days in {topic_context}:

{signal_lines}

Generate a prediction report with this exact JSON structure:
{{
  "emerging_directions": [
    {{"direction": "str", "reasoning": "str", "confidence": "high|medium|low"}},
    {{"direction": "str", "reasoning": "str", "confidence": "high|medium|low"}},
    {{"direction": "str", "reasoning": "str", "confidence": "high|medium|low"}}
  ],
  "underexplored_gaps": [
    {{"gap": "str", "reasoning": "str"}},
    {{"gap": "str", "reasoning": "str"}},
    {{"gap": "str", "reasoning": "str"}}
  ],
  "predicted_convergences": [
    {{"concept_a": "str", "concept_b": "str", "reasoning": "str"}},
    {{"concept_a": "str", "concept_b": "str", "reasoning": "str"}}
  ],
  "time_horizon_months": 12,
  "overall_confidence": "high|medium|low"
}}"""

_FALLBACK_REPORT = PredictionReport(
    emerging_directions=[
        EmergingDirection(direction="Unknown", reasoning="LLM response unavailable", confidence="low"),
        EmergingDirection(direction="Unknown", reasoning="LLM response unavailable", confidence="low"),
        EmergingDirection(direction="Unknown", reasoning="LLM response unavailable", confidence="low"),
    ],
    underexplored_gaps=[
        UnexploredGap(gap="Unknown", reasoning="LLM response unavailable"),
        UnexploredGap(gap="Unknown", reasoning="LLM response unavailable"),
        UnexploredGap(gap="Unknown", reasoning="LLM response unavailable"),
    ],
    predicted_convergences=[
        PredictedConvergence(concept_a="Unknown", concept_b="Unknown", reasoning="LLM response unavailable"),
        PredictedConvergence(concept_a="Unknown", concept_b="Unknown", reasoning="LLM response unavailable"),
    ],
    time_horizon_months=12,
    overall_confidence="low",
)


class PredictionSynthesizer:
    """Prompts Ollama to synthesize graph signals into a structured prediction report.

    Args:
        ollama_url: Ollama base URL (default from settings).
        model: Ollama model name (default from settings).
        timeout: HTTP timeout in seconds (default from settings).
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self._ollama_url = (ollama_url or settings.ollama_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._timeout = timeout or settings.ollama_request_timeout_seconds

    async def synthesize(
        self,
        signals: list[ConceptSignal],
        topic_context: str = "AI/ML research",
    ) -> PredictionReport:
        """Generate a prediction report from concept signals.

        Returns a fallback report (overall_confidence='low') on any error —
        never raises, so the DAG task cannot fail due to LLM issues.
        """
        if not signals:
            log.warning("prediction_synthesizer_empty_signals", topic_context=topic_context)
            return _FALLBACK_REPORT

        prompt = self._build_prompt(signals, topic_context)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "system": _SYSTEM_PROMPT,
                    },
                )
                resp.raise_for_status()
                raw_json: str = resp.json().get("response", "{}")
        except httpx.HTTPError as exc:
            log.warning(
                "prediction_synthesizer_http_error",
                error=str(exc),
                topic_context=topic_context,
            )
            return _FALLBACK_REPORT

        return self._parse(raw_json, topic_context)

    def _build_prompt(self, signals: list[ConceptSignal], topic_context: str) -> str:
        signal_lines = "\n".join(
            f"- {s.concept_name}: centrality={s.centrality_score:.3f}, "
            f"velocity={s.velocity:.1f}, trend={s.trend}"
            for s in signals
        )
        return _USER_PROMPT_TEMPLATE.format(
            topic_context=topic_context,
            signal_lines=signal_lines,
        )

    def _parse(self, raw_json: str, topic_context: str) -> PredictionReport:
        try:
            data = json.loads(raw_json)
            return PredictionReport.model_validate(data)
        except Exception as exc:
            log.warning(
                "prediction_synthesizer_parse_error",
                topic_context=topic_context,
                error=str(exc),
                raw=raw_json[:400],
            )
            return _FALLBACK_REPORT
