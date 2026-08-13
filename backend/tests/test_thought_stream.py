# tests/test_thought_stream.py
import json

from app.database import Base, create_session_factory
from app.models import (
    ActionLog, AgentRun, AgentRunStep, IntelEvent, Mission, MissionEvent, User,
)
from app.services.thought_stream import ThoughtStream


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'ts.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _seed(tmp_path):
    engine, sf = _env(tmp_path)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with sf() as db:
        run = AgentRun(id="r1", user_id="u1", kind="agent", status="completed",
                       input_json="{}", output_json="{}",
                       created_at=now, updated_at=now)
        db.add(run)
        db.flush()
        db.add(AgentRunStep(id="s1", run_id="r1", sequence=1, name="Research Agent active",
                            status="completed", created_at=now))
        db.add(Mission(id="m1", user_id="u1", goal="g", status="completed",
                       created_at=now, updated_at=now))
        db.flush()
        db.add(MissionEvent(id="me1", mission_id="m1", sequence=1, kind="planned",
                            detail_json="{}", created_at=now))
        db.add(ActionLog(id="a1", user_id="u1", source="mission", tool="list_files",
                         args_json="{}", result_json="{}", created_at=now))
        db.add(IntelEvent(id="i1", user_id="u1", kind="brief", severity="info",
                          title="morning brief", summary="summary", created_at=now))
        db.commit()
    return engine, sf


def test_stream_merges_sources(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        items = ThoughtStream(db).stream("u1", limit=10)
        kinds = {i["kind"] for i in items}
        assert {"agent_step", "mission", "action", "intel"} <= kinds
        assert any(i["source"] == "agent" for i in items)
    engine.dispose()


def test_stream_sorted_desc(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        items = ThoughtStream(db).stream("u1", limit=10)
        times = [i["created_at"] for i in items]
        assert times == sorted(times, reverse=True)
    engine.dispose()


def test_stream_limit(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        items = ThoughtStream(db).stream("u1", limit=2)
        assert len(items) == 2
    engine.dispose()


def test_stream_filter_by_source(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        items = ThoughtStream(db).stream("u1", source="action")
        assert len(items) == 1
        assert items[0]["source"] == "action"
    engine.dispose()


def test_stream_other_user_empty(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        assert ThoughtStream(db).stream("u_other") == []
    engine.dispose()


def test_stream_handles_bad_json(tmp_path):
    engine, sf = _env(tmp_path)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with sf() as db:
        db.add(ActionLog(id="a9", user_id="u1", source="mission", tool="x",
                         args_json="not-json{", result_json="also-bad", created_at=now))
        db.commit()
        items = ThoughtStream(db).stream("u1")
        assert len(items) == 1
        assert items[0]["detail"] is not None
    engine.dispose()
