# tests/test_universal_search.py
from app.database import Base, create_session_factory
from app.models import (
    Conversation, Document, Memory, Message, Mission, Project, Reminder, Task, User,
)
from app.services.universal_search import SEARCHABLE_SOURCES, UniversalSearch


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'us.db'}")
    Base.metadata.create_all(engine)
    return engine, sf


def _seed(tmp_path):
    engine, sf = _env(tmp_path)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.flush()
        db.add(Project(id="p1", user_id="u1", name="AURA vision", description="computer vision system"))
        db.add(Conversation(id="c1", user_id="u1", title="AURA planning"))
        db.flush()
        db.add(Message(id="msg1", conversation_id="c1", role="user", content="lets build the aura vision"))
        db.add(Memory(id="mem1", user_id="u1", title="project idea", content="the aura vision system uses cameras"))
        db.add(Document(id="d1", user_id="u1", filename="aura_notes.txt", media_type="text/plain",
                        storage_path="/x", extracted_text="document about the aura vision"))
        db.add(Task(id="t1", user_id="u1", title="ship aura", description="release v1"))
        db.add(Reminder(id="r1", user_id="u1", title="aura standup", message="weekly sync", remind_at=now))
        db.add(Mission(id="m1", user_id="u1", goal="launch the aura vision product", status="completed",
                       created_at=now, updated_at=now))
        db.commit()
    return engine, sf


def test_search_finds_across_sources(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        results = UniversalSearch(db).search("u1", "aura")
        types = {r["type"] for r in results}
        assert {"project", "conversation", "message", "memory", "document", "task", "reminder", "mission"} <= types
    engine.dispose()


def test_search_filtered_sources(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        results = UniversalSearch(db).search("u1", "aura", sources=["memory"])
        assert all(r["type"] == "memory" for r in results)
        assert len(results) == 1
    engine.dispose()


def test_search_other_user_empty(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        assert UniversalSearch(db).search("u_other", "aura") == []
    engine.dispose()


def test_empty_query(tmp_path):
    engine, sf = _seed(tmp_path)
    with sf() as db:
        assert UniversalSearch(db).search("u1", "   ") == []
    engine.dispose()


def test_sources_constant():
    assert "memory" in SEARCHABLE_SOURCES
    assert "missions" in SEARCHABLE_SOURCES
    assert "documents" in SEARCHABLE_SOURCES
