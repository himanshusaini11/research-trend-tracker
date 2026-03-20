"""Unit tests for PredictionSynthesizer — mocks httpx Ollama calls."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.graph.prediction_synthesizer import PredictionSynthesizer
from app.graph.schemas import ConceptSignal, PredictionReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal(name: str, score: float = 0.5) -> ConceptSignal:
    return ConceptSignal(
        concept_name=name,
        centrality_score=score,
        velocity=5.0,
        acceleration=1.0,
        trend="accelerating",
        composite_score=score,
    )


def _valid_report_dict() -> dict:
    return {
        "emerging_directions": [
            {"direction": "Dir A", "reasoning": "R1", "confidence": "high"},
            {"direction": "Dir B", "reasoning": "R2", "confidence": "medium"},
            {"direction": "Dir C", "reasoning": "R3", "confidence": "low"},
        ],
        "underexplored_gaps": [
            {"gap": "Gap 1", "reasoning": "G1"},
            {"gap": "Gap 2", "reasoning": "G2"},
            {"gap": "Gap 3", "reasoning": "G3"},
        ],
        "predicted_convergences": [
            {"concept_a": "A", "concept_b": "B", "reasoning": "R"},
            {"concept_a": "C", "concept_b": "D", "reasoning": "R2"},
        ],
        "time_horizon_months": 12,
        "overall_confidence": "high",
    }


def _mock_client(response_json: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.json.return_value = response_json
    resp.raise_for_status = MagicMock()

    mock = AsyncMock()
    mock.post = AsyncMock(return_value=resp)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def _synth() -> PredictionSynthesizer:
    return PredictionSynthesizer(
        ollama_url="http://localhost:11434",
        model="llama3.2",
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_returns_prediction_report() -> None:
    mock_client = _mock_client({"response": json.dumps(_valid_report_dict())})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("attention")])

    assert isinstance(report, PredictionReport)
    assert report.overall_confidence == "high"
    assert len(report.emerging_directions) == 3
    assert len(report.underexplored_gaps) == 3
    assert len(report.predicted_convergences) == 2


@pytest.mark.asyncio
async def test_synthesize_parses_all_fields() -> None:
    data = _valid_report_dict()
    mock_client = _mock_client({"response": json.dumps(data)})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("transformer")])

    assert report.emerging_directions[0].direction == "Dir A"
    assert report.emerging_directions[0].confidence == "high"
    assert report.underexplored_gaps[0].gap == "Gap 1"
    assert report.predicted_convergences[0].concept_a == "A"
    assert report.time_horizon_months == 12


# ---------------------------------------------------------------------------
# Prompt content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_prompt_contains_concept_names() -> None:
    mock_client = _mock_client({"response": json.dumps(_valid_report_dict())})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        await _synth().synthesize(
            [_signal("attention mechanism", 0.8), _signal("knowledge graph", 0.4)],
            topic_context="NLP research",
        )

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert "attention mechanism" in body["prompt"]
    assert "knowledge graph" in body["prompt"]
    assert "NLP research" in body["prompt"]


@pytest.mark.asyncio
async def test_synthesize_prompt_contains_centrality_and_trend() -> None:
    mock_client = _mock_client({"response": json.dumps(_valid_report_dict())})
    sig = _signal("bert", 0.75)

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        await _synth().synthesize([sig])

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert "0.750" in body["prompt"]  # centrality formatted to 3 dp
    assert "accelerating" in body["prompt"]


@pytest.mark.asyncio
async def test_synthesize_sends_json_format_and_system_prompt() -> None:
    mock_client = _mock_client({"response": json.dumps(_valid_report_dict())})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        await _synth().synthesize([_signal("x")])

    call_kwargs = mock_client.post.call_args
    body = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
    assert body["format"] == "json"
    assert body["stream"] is False
    assert "system" in body
    assert "JSON" in body["system"]


# ---------------------------------------------------------------------------
# Malformed / error responses → fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_malformed_json_returns_fallback() -> None:
    mock_client = _mock_client({"response": "NOT JSON {"})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("x")])

    assert report.overall_confidence == "low"
    assert len(report.emerging_directions) == 3  # fallback still has 3


@pytest.mark.asyncio
async def test_synthesize_wrong_structure_returns_fallback() -> None:
    # Valid JSON but missing required fields
    wrong = {"emerging_directions": [], "overall_confidence": "high"}
    mock_client = _mock_client({"response": json.dumps(wrong)})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("x")])

    assert report.overall_confidence == "low"


@pytest.mark.asyncio
async def test_synthesize_http_error_returns_fallback() -> None:
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("x")])

    assert report.overall_confidence == "low"


@pytest.mark.asyncio
async def test_synthesize_empty_signals_returns_fallback() -> None:
    report = await _synth().synthesize([])
    assert report.overall_confidence == "low"


# ---------------------------------------------------------------------------
# Pydantic validation — exactly 3 emerging_directions enforced
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_too_few_directions_returns_fallback() -> None:
    data = _valid_report_dict()
    data["emerging_directions"] = data["emerging_directions"][:2]  # only 2 instead of 3
    mock_client = _mock_client({"response": json.dumps(data)})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("x")])

    assert report.overall_confidence == "low"


@pytest.mark.asyncio
async def test_synthesize_too_many_directions_returns_fallback() -> None:
    data = _valid_report_dict()
    extra = {"direction": "Extra", "reasoning": "R", "confidence": "low"}
    data["emerging_directions"].append(extra)  # 4 instead of 3
    mock_client = _mock_client({"response": json.dumps(data)})

    with patch("app.graph.prediction_synthesizer.httpx.AsyncClient", return_value=mock_client):
        report = await _synth().synthesize([_signal("x")])

    assert report.overall_confidence == "low"
