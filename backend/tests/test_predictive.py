# tests/test_predictive.py
from datetime import datetime, timedelta, timezone

from app.database import Base, create_session_factory
from app.models import ActionLog, User
from app.services.intel.predictive import PredictiveEngine


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'pred.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _day(offset_days, hour=9):
    base = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=offset_days)


def test_detects_repeated_pattern(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        for d in range(3):
            db.add(ActionLog(id=f"a{d}", user_id="u1", source="chat", tool="open_app",
                             args_json='{"app_name": "VS Code"}', result_json="{}",
                             created_at=_day(d)))
        db.commit()
        patterns = PredictiveEngine(db).patterns("u1")
        assert any(p["tool"] == "open_app" and p["occurrences"] >= 3 for p in patterns)
    engine.dispose()


def test_ignores_single_occurrence(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(ActionLog(id="a1", user_id="u1", source="chat", tool="email_read",
                         args_json="{}", result_json="{}", created_at=_day(0)))
        db.commit()
        assert PredictiveEngine(db).patterns("u1") == []
    engine.dispose()


def test_suggest_now_matches_hour(tmp_path):
    engine, sf = _env(tmp_path)
    hour = 14
    with sf() as db:
        for d in range(3):
            db.add(ActionLog(id=f"a{d}", user_id="u1", source="mission", tool="run_command",
                             args_json="{}", result_json="{}", created_at=_day(d, hour=hour)))
        db.commit()
        pred = PredictiveEngine(db)
        now = datetime.now(timezone.utc).replace(hour=hour)
        suggestions = pred.suggest_now("u1", now=now)
        assert len(suggestions) >= 1
        assert suggestions[0]["tool"] == "run_command"
    engine.dispose()


def test_suggestions_have_text(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        assert "command" in PredictiveEngine._suggestion("run_command")
        assert "open" in PredictiveEngine._suggestion("open_app").lower()
    engine.dispose()
