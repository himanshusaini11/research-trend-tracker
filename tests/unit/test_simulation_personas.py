"""Unit tests for app/simulation/personas.py."""
from __future__ import annotations

import pytest

from app.simulation.personas import (
    ALL_PERSONAS,
    POLICY_MAKER,
    RESEARCHER,
    VENTURE_CAPITALIST,
    Persona,
)


def test_all_personas_count() -> None:
    assert len(ALL_PERSONAS) == 3


def test_all_personas_are_persona_instances() -> None:
    for p in ALL_PERSONAS:
        assert isinstance(p, Persona)


def test_persona_names_are_unique() -> None:
    names = [p.name for p in ALL_PERSONAS]
    assert len(names) == len(set(names))


def test_researcher_temperature() -> None:
    assert RESEARCHER.temperature == 0.3


def test_venture_capitalist_temperature() -> None:
    assert VENTURE_CAPITALIST.temperature == 0.5


def test_policy_maker_temperature() -> None:
    assert POLICY_MAKER.temperature == 0.4


def test_researcher_skepticism_is_high() -> None:
    assert RESEARCHER.skepticism == "high"


def test_vc_skepticism_is_medium() -> None:
    assert VENTURE_CAPITALIST.skepticism == "medium"


def test_policy_maker_skepticism_is_medium() -> None:
    assert POLICY_MAKER.skepticism == "medium"


def test_all_system_prompts_nonempty() -> None:
    for p in ALL_PERSONAS:
        assert len(p.system_prompt) > 50, f"{p.name} system_prompt is too short"


def test_all_system_prompts_require_json_output() -> None:
    for p in ALL_PERSONAS:
        assert "JSON" in p.system_prompt, f"{p.name} system_prompt must mention JSON"


def test_personas_are_frozen() -> None:
    """Persona dataclass is frozen — mutation must raise."""
    with pytest.raises((AttributeError, TypeError)):
        RESEARCHER.temperature = 0.9  # type: ignore[misc]


def test_all_personas_list_order() -> None:
    """Canonical order: researcher, venture_capitalist, policy_maker."""
    assert ALL_PERSONAS[0].name == "researcher"
    assert ALL_PERSONAS[1].name == "venture_capitalist"
    assert ALL_PERSONAS[2].name == "policy_maker"
