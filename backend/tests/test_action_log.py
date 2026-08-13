# tests/test_action_log.py
import json

from app.database import Base, create_session_factory
from app.models import ActionLog, User
from app.services.action_log import ActionLogger


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'act.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_record_and_list(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        logger = ActionLogger(db)
        logger.record(
            user_id="u1", source="mission", tool="list_files",
            args={"path": "/x"}, result={"status": "ok"}, is_undoable=False,
        )
        db.commit()
    with sf() as db:
        logger = ActionLogger(db)
        rows = logger.list_for_user(db, "u1")
        assert len(rows) == 1
        assert rows[0].tool == "list_files"
    engine.dispose()


def test_undo_restores_file(tmp_path):
    engine, sf = _env(tmp_path)
    target = tmp_path / "doc.txt"
    target.write_text("ORIGINAL", encoding="utf-8")

    with sf() as db:
        logger = ActionLogger(db)
        action = logger.record(
            user_id="u1", source="mission", tool="file_write",
            args={"path": str(target), "content": "NEW"},
            result={"status": "ok"},
            is_undoable=True,
            before_state={"path": str(target), "content": "ORIGINAL"},
            undo_action={"tool": "file_write", "args": {"path": str(target), "content": "ORIGINAL"}},
        )
        db.commit()
        action_id = action.id

    target.write_text("NEW", encoding="utf-8")

    with sf() as db:
        logger = ActionLogger(db)
        ok = logger.undo(db, action_id, "u1")
        assert ok is True
        db.commit()

    assert target.read_text(encoding="utf-8") == "ORIGINAL"
    with sf() as db:
        row = db.query(ActionLog).filter(ActionLog.id == action_id).first()
        assert row.undo_status == "undone"
    engine.dispose()


def test_undo_non_undoable_raises(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        logger = ActionLogger(db)
        action = logger.record(
            user_id="u1", source="chat", tool="email_send",
            args={"to": "a@b.com"}, result={"status": "ok"}, is_undoable=False,
        )
        db.commit()
        action_id = action.id
    with sf() as db:
        logger = ActionLogger(db)
        assert logger.undo(db, action_id, "u1") is False
    engine.dispose()


def test_undo_other_user_denied(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(User(id="u2", email="u2@example.com", password_hash="hash"))
        db.commit()
    with sf() as db:
        logger = ActionLogger(db)
        action = logger.record(
            user_id="u1", source="chat", tool="list_files",
            args={}, result={}, is_undoable=False,
        )
        db.commit()
        action_id = action.id
    with sf() as db:
        logger = ActionLogger(db)
        assert logger.undo(db, action_id, "u2") is False
    engine.dispose()
