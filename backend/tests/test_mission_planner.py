# tests/test_mission_planner.py
import json
from unittest.mock import AsyncMock

import pytest

from app.services.missions.planner import MissionPlanner, PlanningError


def _fake_gemini(plan_steps):
    text = json.dumps({"steps": plan_steps})
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value=text)
    return mock


@pytest.mark.asyncio
async def test_plan_valid_output():
    gemini = _fake_gemini([
        {"tool": "list_files", "args": {"path": "/downloads"}, "rationale": "scan"},
        {"tool": "run_command", "args": {"command": "dir /downloads"}, "rationale": "list"},
    ])
    planner = MissionPlanner(gemini)
    steps = await planner.plan("Organize my downloads folder")
    assert len(steps) == 2
    assert steps[0]["tool"] == "list_files"
    assert steps[1]["rationale"] == "list"


@pytest.mark.asyncio
async def test_plan_retries_on_malformed_json():
    bad_text = "Here is the plan:\n"
    good_text = json.dumps({"steps": [{"tool": "list_files", "args": {"path": "."}, "rationale": "ok"}]})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(side_effect=[bad_text, good_text])
    planner = MissionPlanner(gemini)
    steps = await planner.plan("find files")
    assert len(steps) == 1
    assert gemini.chat.call_count == 2


@pytest.mark.asyncio
async def test_plan_fails_after_retries():
    gemini = AsyncMock()
    gemini.chat = AsyncMock(return_value="no json here")
    planner = MissionPlanner(gemini)
    with pytest.raises(PlanningError):
        await planner.plan("do something")
    assert gemini.chat.call_count == 3


@pytest.mark.asyncio
async def test_plan_rejects_unknown_tool():
    text = json.dumps({"steps": [{"tool": "nonexistent_tool_xyz", "args": {}, "rationale": "x"}]})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(side_effect=[text, text, text])
    planner = MissionPlanner(gemini, known_tools={"list_files", "run_command"})
    with pytest.raises(PlanningError):
        await planner.plan("do something")


@pytest.mark.asyncio
async def test_plan_empty_steps_retries():
    empty = json.dumps({"steps": []})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(return_value=empty)
    planner = MissionPlanner(gemini)
    with pytest.raises(PlanningError):
        await planner.plan("do nothing")
