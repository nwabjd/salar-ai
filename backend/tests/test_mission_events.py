# tests/test_mission_events.py
from app.database import Base, create_session_factory
from app.models import Mission, MissionEvent, User, token_id
from app.services.missions.events import MissionEventStore
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)


def _make_mission(db):
    db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
    db.flush()
    m = Mission(id=token_id(), user_id="u1", goal="g", created_at=_utcnow(), updated_at=_utcnow(),
                step_count=0, completed_count=0, total_attempts=0, replan_count=0)
    db.add(m)
    db.commit()
    return m.id


def test_event_append_and_recent(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mev.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        mid = _make_mission(db)
        store = MissionEventStore(db)
        store.append(mid, "planned", {"steps": 3})
        store.append(mid, "step_started", {"tool": "list_files"})
        store.append(mid, "step_completed", {"tool": "list_files"})
        db.commit()

        events = store.recent(mid, limit=10)
        assert len(events) == 3
        assert events[0].kind == "planned"
        assert events[2].kind == "step_completed"


def test_event_since_sequence(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mev2.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        mid = _make_mission(db)
        store = MissionEventStore(db)
        store.append(mid, "planned", {})
        store.append(mid, "step_started", {"tool": "x"})
        store.append(mid, "step_completed", {"tool": "x"})
        db.commit()

        events = store.recent(mid, since_sequence=2)
        assert len(events) == 1
        assert events[0].kind == "step_completed"
