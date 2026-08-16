# tests/test_core_correction.py
from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from app.services.core.correction import SelfCorrectionLoop
from app.services.core.toolspec import ToolRegistry, ToolSpec


@dataclass
class FakeStep:
    id: str = "step1"
    description: str = "fake step"
    tool_name: str = "run_command"
    args: Dict[str, Any] = field(default_factory=dict)


class FakeRegistry(ToolRegistry):
    """Registry whose run() returns controlled results; no real shell execution."""

    def __init__(self, responses=None):
        super().__init__()
        self.responses = responses or {}
        self.calls = []

    async def run(self, name, args, user_id, db_session=None, is_admin=False):
        self.calls.append({"name": name, "args": args})
        if name == "run_command":
            command = str(args.get("command", ""))
            if command.startswith("mkdir -p "):
                return {"exit_code": 0, "stdout": "", "stderr": ""}
            if command.startswith("mkdir "):
                return {"exit_code": 1, "stdout": "", "stderr": "cannot create directory: file exists"}
        return self.responses.get(name, {"exit_code": 0})


@pytest.mark.asyncio
async def test_success_on_first_attempt():
    reg = FakeRegistry()
    loop = SelfCorrectionLoop(registry=reg)
    out = await loop.execute(FakeStep(tool_name="run_command", args={"command": "mkdir -p /tmp/x"}), "u1")
    assert out.status == "completed"
    assert out.verified is True
    assert out.confidence >= 0.95
    assert len(out.attempts) == 1


@pytest.mark.asyncio
async def test_failure_then_alternative_then_verified():
    reg = FakeRegistry()
    loop = SelfCorrectionLoop(registry=reg)
    out = await loop.execute(FakeStep(tool_name="run_command", args={"command": "mkdir /tmp/blocked"}), "u1")
    assert out.status == "completed"
    assert out.verified is True
    assert len(out.attempts) == 2
    assert reg.calls[0]["args"]["command"] == "mkdir /tmp/blocked"
    assert reg.calls[1]["args"]["command"] == "mkdir -p /tmp/blocked"
    assert out.attempts[0]["verifier"]["passed"] is False
    assert out.attempts[1]["verifier"]["passed"] is True


@pytest.mark.asyncio
async def test_budget_exhaustion_is_honest():
    class AlwaysFail(ToolRegistry):
        async def run(self, name, args, user_id, db_session=None, is_admin=False):
            if name == "run_command":
                return {"exit_code": 1, "stderr": "boom"}
            return {"exit_code": 1}

    reg = AlwaysFail()
    loop = SelfCorrectionLoop(registry=reg, max_attempts=3)
    out = await loop.execute(FakeStep(tool_name="run_command", args={"command": "mkdir /tmp/nope"}), "u1")
    assert out.status == "failed"
    assert out.verified is False
    assert len(out.attempts) == 3


@pytest.mark.asyncio
async def test_never_reports_success_without_verifier():
    class FakeOk(ToolRegistry):
        async def run(self, name, args, user_id, db_session=None, is_admin=False):
            return {"exit_code": 0, "stdout": "ok"}

    reg = FakeOk()
    loop = SelfCorrectionLoop(registry=reg)
    # The run_command verifier checks exit_code == 0, so this genuinely succeeds.
    out = await loop.execute(FakeStep(tool_name="run_command", args={"command": "true"}), "u1")
    assert out.verified is True


@pytest.mark.asyncio
async def test_correction_event_published():
    from app.services.core.events import CORRECTION_ATTEMPT, CoreBus, CoreEvent

    class Bus:
        def __init__(self):
            self.published = []

        async def publish(self, event):
            self.published.append(event)

    reg = FakeRegistry()
    bus = Bus()
    loop = SelfCorrectionLoop(registry=reg, bus=bus)
    await loop.execute(FakeStep(tool_name="run_command", args={"command": "mkdir /tmp/x"}), "u1", trace_id="tr1")
    types = [e.type for e in bus.published]
    assert CORRECTION_ATTEMPT in types
