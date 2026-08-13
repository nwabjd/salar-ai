# tests/test_mission_runner.py
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.database import Base, create_session_factory
from app.models import Mission, MissionStep, MissionEvent, User, token_id
from app.services.missions.runner import MissionRunner, MissionConflict


def _utcnow():
    return datetime.now(timezone.utc)


def _make_runner(tmp_path, *, fake_tool_result=None, plan_steps=None):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'runner.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()

    async def fake_execute_tool(name, args, uid, db, is_admin=False):
        if fake_tool_result is not None:
            return fake_tool_result
        return {"status": "ok", "tool": name}

    async def fake_chat(messages):
        import json
        steps = plan_steps or [{"tool": "list_files", "args": {"path": "."}, "rationale": "scan"}]
        return json.dumps({"steps": steps})

    gemini = AsyncMock()
    gemini.chat = fake_chat

    runner = MissionRunner(
        session_factory=sf,
        gemini=gemini,
        execute_tool_fn=fake_execute_tool,
    )
    return engine, sf, runner


@pytest.mark.asyncio
async def test_launch_happy_path(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        mission = await runner.launch("u1", "organize my downloads")
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
            assert m.step_count == 1
            assert m.completed_count == 1
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            assert len(steps) == 1
            assert steps[0].status == "completed"
            events = db.scalars(
                __import__("sqlalchemy").select(MissionEvent)
                .where(MissionEvent.mission_id == mission["id"])
            ).all()
            assert any(e.kind == "step_completed" for e in events)
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_launch_rejects(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        await runner.launch("u1", "goal one")
        with pytest.raises(MissionConflict):
            await runner.launch("u1", "goal two")
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_dangerous_step_waits_for_approval(tmp_path):
    def danger_classify(tool, args):
        return "dangerous" if tool == "run_command" else "safe"

    engine, sf, runner = await asyncio.to_thread(
        _make_runner, tmp_path,
        plan_steps=[{"tool": "run_command", "args": {"command": "dir"}, "rationale": "list"}],
    )
    runner._classify_tool = danger_classify

    try:
        await runner.start()
        mission = await runner.launch("u1", "run a command")
        await asyncio.sleep(0.2)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "waiting_approval"
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            assert steps[0].status == "waiting_approval"
        await runner.approve(mission["id"], steps[0].id)
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_deny_skips_step(tmp_path):
    def danger_classify(tool, args):
        return "dangerous" if tool == "email_send" else "safe"

    engine, sf, runner = await asyncio.to_thread(
        _make_runner, tmp_path,
        plan_steps=[{"tool": "email_send", "args": {"to": "a@b.com"}, "rationale": "send"}],
    )
    runner._classify_tool = danger_classify

    try:
        await runner.start()
        mission = await runner.launch("u1", "send email")
        await asyncio.sleep(0.2)
        with sf() as db:
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            step_id = steps[0].id
        await runner.deny(mission["id"], step_id, note="not now")
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_cancel(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        mission = await runner.launch("u1", "do something")
        # Cancel immediately: the mission task has not started yet, so the
        # mission is still "queued" and cancel is deterministic.
        await runner.cancel(mission["id"])
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "cancelled"
    finally:
        await runner.stop()
        engine.dispose()
