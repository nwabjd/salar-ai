# tests/test_proactive.py
from datetime import datetime, timedelta, timezone

from app.database import Base, create_session_factory
from app.models import ActionLog, Reminder, Task, User
from app.services.intel.proactive import DETECTORS, ProactiveDetector
from app.services.intel.events import IntelEventStore


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'pro.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _now():
    return datetime.now(timezone.utc)


def test_detectors_constant():
    assert "low_storage" in DETECTORS
    assert "failed_builds" in DETECTORS
    assert "unusual_cpu" in DETECTORS


def test_low_storage_warns(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        d = ProactiveDetector(db)
        assert d.scan_low_storage("u1", free_pct=5) == 1
        assert d.scan_low_storage("u1", free_pct=5) == 0  # dedup
        db.commit()
    engine.dispose()


def test_high_cpu_warns(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        d = ProactiveDetector(db)
        assert d.scan_cpu("u1", cpu_pct=99) == 1
        db.commit()
    engine.dispose()


def test_upcoming_deadline(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Task(id="t1", user_id="u1", title="ship v1", status="todo", due_date=_now() + timedelta(hours=2)))
        db.commit()
        d = ProactiveDetector(db)
        assert d.scan_upcoming("u1") == 1
        db.commit()
    engine.dispose()


def test_failed_build_detected(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(ActionLog(id="a1", user_id="u1", source="chat", tool="run_command",
                         args_json="{}", result_json='{"status": "error: build failed"}',
                         created_at=_now()))
        db.commit()
        d = ProactiveDetector(db)
        assert d.scan_failed_builds("u1") == 1
        db.commit()
    engine.dispose()


def test_overdue_reminder(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Reminder(id="r1", user_id="u1", title="call dad", is_done=False,
                        remind_at=_now() - timedelta(days=1)))
        db.commit()
        d = ProactiveDetector(db)
        assert d.scan_overdue_reminders("u1") == 1
        db.commit()
    engine.dispose()


def test_scan_records_intel(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        d = ProactiveDetector(db)
        n = d.scan("u1", storage_free_pct=4, cpu_pct=99)
        assert n >= 2
        db.commit()
        kinds = {e.kind for e in IntelEventStore(db).recent("u1", limit=20)}
        assert "low_storage" in kinds
        assert "high_cpu" in kinds
    engine.dispose()
