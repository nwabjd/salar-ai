# tests/test_eod_memory.py
from datetime import datetime, timedelta, timezone

from app.database import Base, create_session_factory
from app.models import ActionLog, IntelEvent, Mission, Task, User
from app.services.intel.eod_memory import EndOfDayMemory


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'eod.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _now():
    return datetime.now(timezone.utc)


def test_build_counts_completed(tmp_path):
    engine, sf = _env(tmp_path)
    now = _now()
    with sf() as db:
        db.add(Mission(id="m1", user_id="u1", goal="launch", status="completed",
                       finished_at=now, created_at=now, updated_at=now))
        db.add(Task(id="t1", user_id="u1", title="done task", status="done",
                    created_at=now, updated_at=now))
        db.add(ActionLog(id="a1", user_id="u1", source="chat", tool="list_files",
                         args_json="{}", result_json="{}", created_at=now))
        db.commit()
        summary = EndOfDayMemory(db).build("u1")
        assert len(summary["completed"]["missions"]) == 1
        assert len(summary["completed"]["tasks"]) == 1
        assert summary["completed"]["actions"] == 1
    engine.dispose()


def test_build_unfinished(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Task(id="t1", user_id="u1", title="open task", status="todo",
                    created_at=_now(), updated_at=_now()))
        db.commit()
        summary = EndOfDayMemory(db).build("u1")
        assert any(t["title"] == "open task" for t in summary["unfinished"]["tasks"])
    engine.dispose()


def test_record_dedup(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        eod = EndOfDayMemory(db)
        assert eod.record("u1") is True
        assert eod.record("u1") is False
        events = db.scalars(__import__("sqlalchemy").select(IntelEvent).where(IntelEvent.kind == "eod")).all()
        assert len(events) == 1
    engine.dispose()


def test_record_persists_summary(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        assert EndOfDayMemory(db).record("u1") is True
    with sf() as db:
        events = db.scalars(__import__("sqlalchemy").select(IntelEvent).where(IntelEvent.kind == "eod")).all()
        assert len(events) == 1
        import json
        data = json.loads(events[0].summary)
        assert "completed" in data
    engine.dispose()


def test_api_build(client, exchange):
    headers = exchange("eod-api@example.com")
    me = client.get("/api/auth/me", headers=headers).json()
    now = _now()
    with client.app.state.SessionLocal() as db:
        db.add(Task(id="t-api", user_id=me["id"], title="api done task", status="done",
                    created_at=now, updated_at=now))
        db.commit()
    r = client.get("/api/eod", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["completed"]["tasks"]) == 1
    assert data["completed"]["tasks"][0]["title"] == "api done task"


def test_api_record(client, exchange):
    headers = exchange("eod-rec@example.com")
    r = client.post("/api/eod/record", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"recorded": True}
    r2 = client.post("/api/eod/record", headers=headers)
    assert r2.status_code == 200
    assert r2.json() == {"recorded": False}
