# tests/test_contact_intel.py
from app.database import Base, create_session_factory
from app.models import ContactInteraction, ContactProfile, User
from app.services.contact_intel import ContactIntelligence, INTERACTION_KINDS

import pytest


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'ci.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_kinds():
    assert {"conversation", "meeting", "project", "follow_up", "note"} <= INTERACTION_KINDS


def test_upsert_creates_and_updates(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ci = ContactIntelligence(db)
        p1 = ci.upsert("u1", "Alice", email="a@b.com")
        db.commit()
        p2 = ci.upsert("u1", "Alice", notes="met at conf")
        db.commit()
        assert p1.id == p2.id
        assert p2.notes == "met at conf"
        assert p2.email == "a@b.com"
    engine.dispose()


def test_list_profiles(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ci = ContactIntelligence(db)
        ci.upsert("u1", "Alice")
        ci.upsert("u1", "Bob")
        db.commit()
        assert {p["name"] for p in ci.list_profiles("u1")} == {"Alice", "Bob"}
    engine.dispose()


def test_record_interaction_and_brief(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ci = ContactIntelligence(db)
        ci.record_interaction("u1", "Alice", "meeting", {"topic": "planning"})
        ci.record_interaction("u1", "Alice", "follow_up", {"task": "send deck"})
        db.commit()
        profiles = ci.list_profiles("u1")
        brief = ci.brief("u1", profiles[0]["id"])
        assert brief["name"] == "Alice"
        assert len(brief["interactions"]) == 2
        assert len(brief["pending_follow_ups"]) == 1
    engine.dispose()


def test_record_interaction_invalid_kind(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        with pytest.raises(ValueError):
            ContactIntelligence(db).record_interaction("u1", "Alice", "banana")
    engine.dispose()


def test_brief_other_user_denied(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(User(id="u2", email="u2@example.com", password_hash="hash"))
        ci = ContactIntelligence(db)
        ci.upsert("u1", "Alice")
        db.commit()
        contact_id = ci.list_profiles("u1")[0]["id"]
        with pytest.raises(ValueError):
            ci.brief("u2", contact_id)
    engine.dispose()


def test_interaction_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(ContactProfile(id="c1", user_id="u1", name="Alice"))
        db.commit()
        db.add(ContactInteraction(id="i1", user_id="u1", contact_id="c1", kind="note", detail_json="{}"))
        db.commit()
        assert db.get(ContactInteraction, "i1").kind == "note"
    engine.dispose()
