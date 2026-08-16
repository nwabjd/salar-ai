# tests/test_core_models.py
from app.database import Base, create_session_factory
from app.models import CoreEventLog, CoreTask, CoreTrace, CoreTraceStep, User


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'core.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_core_task_roundtrip(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(CoreTask(id="t1", user_id="u1", request="create folder x", intent_kind="action"))
        db.commit()
        t = db.get(CoreTask, "t1")
        assert t.status == "queued"
        assert t.confidence == 0.0
        assert t.intent_kind == "action"
    engine.dispose()


def test_core_trace_links_task(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(CoreTask(id="t1", user_id="u1", request="run a thing"))
        db.commit()
        db.add(CoreTrace(id="tr1", task_id="t1", status="running"))
        db.commit()
        tr = db.get(CoreTrace, "tr1")
        assert tr.steps_count == 0
        assert tr.task_id == "t1"
    engine.dispose()


def test_core_trace_step_links_trace(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(CoreTask(id="t1", user_id="u1", request="r"))
        db.commit()
        db.add(CoreTrace(id="tr1", task_id="t1"))
        db.commit()
        db.add(CoreTraceStep(id="s1", trace_id="tr1", stage="brain", detail_json="{}"))
        db.commit()
        s = db.get(CoreTraceStep, "s1")
        assert s.stage == "brain"
        assert s.duration_ms is None
    engine.dispose()


def test_core_event_log(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(CoreEventLog(id="e1", trace_id="tr1", event_type="TASK_STARTED", payload="{}"))
        db.commit()
        e = db.get(CoreEventLog, "e1")
        assert e.event_type == "TASK_STARTED"
    engine.dispose()
