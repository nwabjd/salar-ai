# tests/test_core_runtime.py
from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from app.database import Base, create_session_factory
from app.models import AgentRun, AgentRunStep, User
from app.services.core.brain import PlanStep
from app.services.core.correction import SelfCorrectionLoop
from app.services.core.events import CoreBus, TOOL_CALLED, AGENT_SPAWNED, AGENT_FINISHED
from app.services.core.runtime import AgentRuntime
from app.services.core.toolspec import ToolRegistry


@dataclass
class FakeStep:
    id: str = "s1"
    description: str = "create folder"
    tool_name: str = "run_command"
    args: Dict[str, Any] = field(default_factory=lambda: {"command": "mkdir -p /tmp/test"})


class FakeRegistry(ToolRegistry):
    async def run(self, name, args, user_id, db_session=None, is_admin=False):
        if name == "run_command":
            cmd = str(args.get("command", ""))
            if cmd.startswith("mkdir -p "):
                return {"exit_code": 0}
            return {"exit_code": 1, "stderr": "file exists"}
        return {"exit_code": 0}


class RecorderBus(CoreBus):
    def __init__(self):
        super().__init__(db_factory=None)
        self.recorded = []

    async def publish(self, event):
        self.recorded.append(event)


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'rt.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


@pytest.mark.asyncio
async def test_spawn_run_retire_lifecycle(tmp_path):
    engine, sf = _env(tmp_path)
    bus = RecorderBus()
    reg = FakeRegistry()
    loop = SelfCorrectionLoop(registry=reg, bus=bus)
    runtime = AgentRuntime(bus=bus, correction=loop)

    with sf() as db:
        run = await runtime.spawn("u1", "System", "create folder x", trace_id="tr1", db_session=db)
        assert run.status == "running"
        assert bus.recorded[-1].type == AGENT_SPAWNED
        assert len(runtime.live_agents(db_session=db)) == 1

        result = await runtime.run(run.id, [FakeStep()], "u1", db_session=db, trace_id="tr1")
        assert result["status"] == "completed"
        assert result["confidence"] >= 0.9

        await runtime.retire(run.id, db_session=db, trace_id="tr1")
        assert runtime.live_agents(db_session=db) == []

        run = db.get(AgentRun, run.id)
        assert run.status == "completed"
        steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).all()
        assert len(steps) == 1
        assert steps[0].sequence == 1
        assert "passed" in steps[0].evidence_json
    engine.dispose()


@pytest.mark.asyncio
async def test_run_publishes_tool_and_verification_events(tmp_path):
    engine, sf = _env(tmp_path)
    bus = RecorderBus()
    reg = FakeRegistry()
    loop = SelfCorrectionLoop(registry=reg, bus=bus)
    runtime = AgentRuntime(bus=bus, correction=loop)

    with sf() as db:
        run = await runtime.spawn("u1", "System", "create folder x", trace_id="tr2", db_session=db)
        await runtime.run(run.id, [FakeStep(description="mkdir step")], "u1", db_session=db, trace_id="tr2")
        await runtime.retire(run.id, db_session=db, trace_id="tr2")

    types = [e.type for e in bus.recorded]
    assert AGENT_SPAWNED in types
    assert TOOL_CALLED in types
    assert AGENT_FINISHED in types
    assert any("VERIFICATION_PASSED" == t for t in types)
    engine.dispose()


@pytest.mark.asyncio
async def test_run_marks_failed_when_step_never_verifies(tmp_path):
    engine, sf = _env(tmp_path)
    bus = RecorderBus()

    class AlwaysFail(ToolRegistry):
        async def run(self, name, args, user_id, db_session=None, is_admin=False):
            return {"exit_code": 1, "stderr": "boom"}

    runtime = AgentRuntime(bus=bus, correction=SelfCorrectionLoop(registry=AlwaysFail(), bus=bus))
    with sf() as db:
        run = await runtime.spawn("u1", "System", "x", trace_id="tr3", db_session=db)
        result = await runtime.run(run.id, [FakeStep()], "u1", db_session=db, trace_id="tr3")
        assert result["status"] == "failed"
        assert result["confidence"] == 0.0
    engine.dispose()


@pytest.mark.asyncio
async def test_multiple_steps_have_increasing_sequence(tmp_path):
    engine, sf = _env(tmp_path)
    bus = RecorderBus()
    runtime = AgentRuntime(bus=bus, correction=SelfCorrectionLoop(registry=FakeRegistry(), bus=bus))
    with sf() as db:
        run = await runtime.spawn("u1", "System", "x", trace_id="tr4", db_session=db)
        steps = [FakeStep(id="a", description="step one"), FakeStep(id="b", description="step two")]
        await runtime.run(run.id, steps, "u1", db_session=db, trace_id="tr4")
        rows = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).order_by(AgentRunStep.sequence).all()
        assert [r.sequence for r in rows] == [1, 2]
    engine.dispose()
