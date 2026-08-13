# tests/test_decision_simulator.py
import json
from unittest.mock import AsyncMock

import pytest

from app.services.decision_simulator import DecisionSimulator, DecisionSimulatorError


def _mock_gemini(response=None):
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value=response or json.dumps({
        "scenarios": [
            {"option": "A", "assumptions": ["x"], "risks": ["y"], "likely_outcome": "ok", "probability_of_success": 0.8},
            {"option": "B", "assumptions": ["z"], "risks": ["w"], "likely_outcome": "risky", "probability_of_success": 0.4},
        ],
        "comparison": "A is safer but slower.",
        "recommendation": "A",
    }))
    return mock


@pytest.mark.asyncio
async def test_simulate_returns_structured():
    sim = DecisionSimulator(gemini=_mock_gemini())
    result = await sim.simulate("hire or build?", ["hire", "build"])
    assert result["question"] == "hire or build?"
    assert len(result["scenarios"]) == 2
    assert result["recommendation"] in ("A", "B", "mixed")
    assert "probability_of_success" in result["scenarios"][0]


@pytest.mark.asyncio
async def test_no_gemini_raises():
    with pytest.raises(DecisionSimulatorError):
        await DecisionSimulator(gemini=None).simulate("q", ["a", "b"])


@pytest.mark.asyncio
async def test_too_few_options_raises():
    with pytest.raises(DecisionSimulatorError):
        await DecisionSimulator(gemini=_mock_gemini()).simulate("q", ["only"])


@pytest.mark.asyncio
async def test_malformed_response_fallback():
    sim = DecisionSimulator(gemini=_mock_gemini(response="not json at all"))
    result = await sim.simulate("q", ["a", "b"])
    assert result["comparison"] == "not json at all"
    assert result["recommendation"] == "mixed"
    assert len(result["scenarios"]) == 2
