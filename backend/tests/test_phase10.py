# tests/test_phase10.py
import pytest

from app.database import Base, create_session_factory
from app.models import Device, PushToken, SyncState, User
from app.services.multi_device import REMOTE_ACTIONS, MultiDevice

from datetime import datetime, timezone


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p10.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
        db.add(Device(id="d1", user_id="u1", name="laptop", token_hash="h", platform="windows"))
        db.add(Device(id="d2", user_id="u1", name="phone", token_hash="h2", platform="android"))
        db.commit()
    return engine, sf


def test_remote_actions_constant():
    assert {"wake", "lock", "shutdown", "screenshot", "open_app", "notification"} <= REMOTE_ACTIONS


def test_touch_updates_last_seen(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        md = MultiDevice(db)
        state = md.touch("u1", "d1")
        db.commit()
        assert state.pending_commands == 0
        assert db.get(Device, "d1").last_seen_at is not None
    engine.dispose()


def test_touch_unknown_device_raises(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        with pytest.raises(ValueError):
            MultiDevice(db).touch("u1", "nope")
    engine.dispose()


def test_remote_queues_command(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        md = MultiDevice(db)
        r = md.remote("u1", "d1", "open_app", {"app": "vscode"})
        db.commit()
        assert r["status"] == "queued"
        pending = md.pending_for("u1", "d1")
        assert len(pending) == 1
        assert pending[0]["kind"] == "remote_open_app"
    engine.dispose()


def test_remote_destructive_requires_confirmation(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        r = MultiDevice(db).remote("u1", "d1", "shutdown")
        db.commit()
        assert r["requires_confirmation"] is True
    engine.dispose()


def test_remote_invalid_action(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        r = MultiDevice(db).remote("u1", "d1", "teleport")
        assert r["status"] == "error"
    engine.dispose()


def test_offline_since(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        device = db.get(Device, "d2")
        device.last_seen_at = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=3)
        db.commit()
        offline = MultiDevice(db).offline_since("u1", minutes=5)
        assert any(d["id"] == "d2" for d in offline)
    engine.dispose()


def test_push_register_dedup(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        md = MultiDevice(db)
        p1 = md.register_push("u1", "tok-1", "web_push", device_id="d1")
        p2 = md.register_push("u1", "tok-1", "fcm")
        db.commit()
        assert p1.id == p2.id
        assert len(md.list_push_tokens("u1")) == 1
    engine.dispose()


def test_push_unregister(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        md = MultiDevice(db)
        md.register_push("u1", "tok-2", "fcm")
        db.commit()
        tokens = md.list_push_tokens("u1")
        assert md.unregister_push("u1", tokens[0]["id"]) is True
        db.commit()
        assert md.list_push_tokens("u1") == []
    engine.dispose()


def test_push_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(PushToken(id="pt1", user_id="u1", device_id="d1", platform="fcm", token="t"))
        db.commit()
        assert db.get(PushToken, "pt1").platform == "fcm"
    engine.dispose()


def test_sync_state_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(SyncState(id="s1", user_id="u1", device_id="d1", pending_commands=2))
        db.commit()
        assert db.get(SyncState, "s1").pending_commands == 2
    engine.dispose()
