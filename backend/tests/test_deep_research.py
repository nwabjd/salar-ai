# tests/test_deep_research.py
import json
from unittest.mock import AsyncMock

import pytest

from app.database import Base, create_session_factory
from app.models import DeepResearch, User
from app.services.deep_research import DeepResearchError, DeepResearchMode


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'dr.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _mock_gemini(research_responses=None, synth_response=None):
    """Gemini mock: returns different text per call: research agents first, then synthesis."""
    r1 = research_responses or ["Finding A: clear evidence suggests X.", "Challenge: source Y contradicts.", "Practical note: Z is often overlooked."]
    synth = synth_response or json.dumps({"synthesis": "Verified: X is supported", "confidence": "high", "consensus_points": ["X"], "contradictions": [], "unresolved": [], "sources_cited": []})
    all_responses = r1 + [synth]
    mock = AsyncMock()
    mock.chat = AsyncMock(side_effect=all_responses)
    return mock


@pytest.mark.asyncio
async def test_run_returns_synthesis(tmp_path):
    engine, sf = _env(tmp_path)
    mode = DeepResearchMode(gemini=_mock_gemini())
    result = await mode.run("What is the best camera?")
    assert result["num_agents"] == 3
    assert len(result["findings"]) == 3
    assert result["synthesis"]["synthesis"] == "Verified: X is supported"
    engine.dispose()


@pytest.mark.asyncio
async def test_no_gemini_raises():
    with pytest.raises(DeepResearchError):
        await DeepResearchMode(gemini=None).run("test")


def test_store_persists(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        mode = DeepResearchMode()
        row = mode.store(db, "u1", {"goal": "test", "findings": [{"x": 1}], "synthesis": {"y": 2}})
        db.commit()
        loaded = db.get(DeepResearch, row.id)
        assert loaded.goal == "test"
        assert json.loads(loaded.synthesis_json)["y"] == 2
    engine.dispose()


@pytest.mark.asyncio
async def test_synthesis_malformed_fallback(tmp_path):
    engine, sf = _env(tmp_path)
    mock = AsyncMock()
    mock.chat = AsyncMock(side_effect=["agent1", "agent2", "not json at all"])
    mode = DeepResearchMode(gemini=mock)
    result = await mode.run("x", num_agents=2)
    assert result["synthesis"]["synthesis"] == "not json at all"
    assert result["synthesis"]["confidence"] == "medium"
    engine.dispose()
