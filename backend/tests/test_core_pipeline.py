# tests/test_core_pipeline.py
from typing import Any, Dict

import pytest

from app.database import Base, create_session_factory
from app.models import CoreTask, CoreTrace, CoreTraceStep, User
from app.services.core.brain import CoreBrain, CorePlan, PlanStep
from app.services.core.confidence import ConfidenceSystem
from app.services.core.correction import SelfCorrectionLoop
from app.services.core.events import CoreBus, TASK_COMPLETED, TASK_FAILED
from app.services.core.pipeline import CorePipeline
from app.services.core.runtime import AgentRuntime
from app.services.core.supervisor import Supervisor
from app.services.core.toolspec import ToolRegistry
from app.services.core.verification import VerificationEngine


class FakeRegistry(ToolRegistry):
    def __init__(self, fails_first: bool = False, always_fail: bool = False):
        super().__init__()
        self.calls = []
        self.fails_first = fails_first
        self.always_fail = always_fail

    async def run(self, name, args, user_id, db_session=None, is_admin=False):
        self.calls.append((name, dict(args)))
        if name == "run_command":
            cmd = str(args.get("command", ""))
            if self.always_fail:
                return {"exit_code": 1, "stderr": "boom"}
            if self.fails_first and len(self.calls) == 1:
                return {"exit_code": 1, "stderr": "retry me"}
            if cmd.startswith("mkdir -p "):
                return {"exit_code": 0}
            return {"exit_code": 1, "stderr": "file exists"}
        if name == "file_write":
            return {"ok": True, "path": args.get("path", "")}
        if name == "send_message":
            return {"ok": True}
        return {"ok": True, "exit_code": 0}


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'pipeline.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _pipeline(sf, registry):
    bus = CoreBus(db_factory=sf)
    correction = SelfCorrectionLoop(registry=registry, verifier=VerificationEngine(), confidence=ConfidenceSystem(), bus=bus)
    runtime = AgentRuntime(bus=bus, correction=correction)
    brain = CoreBrain(registry=registry)
    supervisor = Supervisor(bus=bus, registry=registry)
    pipeline = CorePipeline(brain=brain, runtime=runtime, bus=bus, supervisor=supervisor, db_factory=sf, confidence=ConfidenceSystem())
    return pipeline


@pytest.mark.asyncio
async def test_happy_path_completed(tmp_path):
    engine, sf = _env(tmp_path)
    pipeline = _pipeline(sf, FakeRegistry())
    with sf() as db:
        result = await pipeline.run("create folder test_dir_core", "u1", db_session=db)
        assert result.status == "completed"
        assert result.confidence >= 0.7
        assert any("test_dir_core" in v for v in result.verified)
        assert result.attempted and len(result.verified) == len(result.attempted)
        assert TASK_COMPLETED in result.events

        trace = db.query(CoreTrace).filter(CoreTrace.id == result.trace_id).first()
        assert trace is not None and trace.status == "completed"
        steps = db.query(CoreTraceStep).filter(CoreTraceStep.trace_id == result.trace_id).all()
        assert len(steps) >= 5
        task = db.query(CoreTask).filter(CoreTask.trace_id == result.trace_id).first()
        assert task is not None and task.status == "completed"
    engine.dispose()


@pytest.mark.asyncio
async def test_approval_path_halts_without_execution(tmp_path):
    engine, sf = _env(tmp_path)

    class RiskyBrain(CoreBrain):
        def plan(self, intent):
            return CorePlan(
                steps=[PlanStep(id="s1", tool_name="code_run", args={"code": "rm -rf /x"}, description="risky step", needs_approval=True)],
                requires_approval=True,
            )

    registry = FakeRegistry()
    bus = CoreBus(db_factory=sf)
    correction = SelfCorrectionLoop(registry=registry, verifier=VerificationEngine(), confidence=ConfidenceSystem(), bus=bus)
    runtime = AgentRuntime(bus=bus, correction=correction)
    pipeline = CorePipeline(brain=RiskyBrain(registry=registry), runtime=runtime, bus=bus, supervisor=Supervisor(bus=bus), db_factory=sf, confidence=ConfidenceSystem())

    with sf() as db:
        result = await pipeline.run("run dangerous code", "u1", db_session=db)
        assert result.status == "awaiting_approval"
        assert result.attempted == []
        assert registry.calls == []
        task = db.query(CoreTask).order_by(CoreTask.created_at.desc()).first()
        assert task.status == "awaiting_approval"
    engine.dispose()


@pytest.mark.asyncio
async def test_approve_resumes_to_completed(tmp_path, monkeypatch):
    engine, sf = _env(tmp_path)
    registry = FakeRegistry()
    pipeline = _pipeline(sf, registry)
    state = {"calls": 0}

    def flaky_plan(intent):
        state["calls"] += 1
        if state["calls"] == 1:
            return CorePlan(
                steps=[PlanStep(id="s1", tool_name="code_run", args={"code": "x"}, description="risky step", needs_approval=True)],
                requires_approval=True,
            )
        return CorePlan(
            steps=[PlanStep(id="s1", tool_name="run_command", args={"command": "mkdir -p /tmp/ok"}, description="create folder /tmp/ok")],
            requires_approval=False,
        )

    monkeypatch.setattr(pipeline.brain, "plan", flaky_plan)
    with sf() as db:
        first = await pipeline.run("do the thing", "u1", db_session=db)
        assert first.status == "awaiting_approval"
        task = db.query(CoreTask).filter(CoreTask.trace_id == first.trace_id).first()
        result = await pipeline.approve(task.id, False, db_session=db)
        assert result.status == "denied"
    engine.dispose()


@pytest.mark.asyncio
async def test_approve_true_resumes_to_completed(tmp_path, monkeypatch):
    engine, sf = _env(tmp_path)
    registry = FakeRegistry()
    pipeline = _pipeline(sf, registry)
    state = {"calls": 0}

    def flaky_plan(intent):
        state["calls"] += 1
        if state["calls"] == 1:
            return CorePlan(
                steps=[PlanStep(id="s1", tool_name="code_run", args={"code": "x"}, description="risky step", needs_approval=True)],
                requires_approval=True,
            )
        return CorePlan(
            steps=[PlanStep(id="s1", tool_name="run_command", args={"command": "mkdir -p /tmp/ok"}, description="create folder /tmp/ok")],
            requires_approval=False,
        )

    monkeypatch.setattr(pipeline.brain, "plan", flaky_plan)
    with sf() as db:
        first = await pipeline.run("do the thing", "u1", db_session=db)
        assert first.status == "awaiting_approval"
        task = db.query(CoreTask).filter(CoreTask.trace_id == first.trace_id).first()
        result = await pipeline.approve(task.id, True, db_session=db)
        assert result.status == "completed"
        assert any("ok" in v for v in result.verified)
    engine.dispose()


@pytest.mark.asyncio
async def test_correction_path_recovers_after_failed_first_attempt(tmp_path):
    engine, sf = _env(tmp_path)
    registry = FakeRegistry(fails_first=True)
    pipeline = _pipeline(sf, registry)
    with sf() as db:
        result = await pipeline.run("create folder test_dir_core", "u1", db_session=db)
        assert result.status == "completed"
        assert len(registry.calls) >= 2
    engine.dispose()


@pytest.mark.asyncio
async def test_failure_path_marks_failed(tmp_path):
    engine, sf = _env(tmp_path)
    registry = FakeRegistry(always_fail=True)
    pipeline = _pipeline(sf, registry)
    with sf() as db:
        result = await pipeline.run("create folder test_dir_core", "u1", db_session=db)
        assert result.status == "failed"
        assert result.confidence == 0.0
        assert result.attempted
        assert result.verified == []
        assert len(registry.calls) == 3
        assert TASK_FAILED in result.events
    engine.dispose()
