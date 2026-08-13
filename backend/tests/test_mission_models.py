# tests/test_mission_models.py
from datetime import datetime, timezone
from app.database import Base, create_session_factory
from app.models import Mission, MissionStep, MissionEvent, User, token_id


def _utcnow():
    return datetime.now(timezone.utc)


def test_mission_crud(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mission.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.flush()

        m = Mission(
            id=token_id(), user_id="u1", goal="Clean my downloads", mode="autonomous",
            status="queued", step_count=0, completed_count=0, total_attempts=0, replan_count=0,
            created_at=_utcnow(), updated_at=_utcnow(),
        )
        db.add(m)
        db.flush()

        s = MissionStep(
            id=token_id(), mission_id=m.id, sequence=1, tool="list_files",
            args_json="{}", danger_level="safe", status="pending",
            output_json="{}", error="", approval_note="", created_at=_utcnow(),
        )
        db.add(s)
        db.flush()

        e = MissionEvent(
            id=token_id(), mission_id=m.id, sequence=1, kind="planned",
            detail_json="{}", created_at=_utcnow(),
        )
        db.add(e)
        db.commit()

        assert db.get(Mission, m.id).goal == "Clean my downloads"
        assert db.get(MissionStep, s.id).tool == "list_files"
        assert db.get(MissionEvent, e.id).kind == "planned"
