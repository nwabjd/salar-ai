# tests/test_phase5.py
import json

from app.database import Base, create_session_factory
from app.models import ActionLog, Bookmark, KnowledgeChunk, KnowledgeDocument, Memory, Task, User
from app.services.bookmarks import BookmarkManager
from app.services.intel.dynamic_memory import DynamicMemory
from app.services.intel.knowledge_viz import KnowledgeVisualization
from app.services.intel.doc_chunker import chunk_sentences, chunk_with_metadata
from app.services.intel.insights import InsightEngine
from app.services.intel.email_classifier import classify_with_rules

from datetime import datetime, timezone


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p5.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _now():
    return datetime.now(timezone.utc)


def test_bookmark_add_dedup(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        bm = BookmarkManager(db)
        b1 = bm.add("u1", "https://a.com", title="A")
        b2 = bm.add("u1", "https://a.com", title="A updated")
        db.commit()
        assert b1.id == b2.id
        items = bm.list("u1")
        assert len(items) == 1
        assert items[0]["title"] == "A updated"
    engine.dispose()


def test_bookmark_search_and_delete(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        bm = BookmarkManager(db)
        bm.add("u1", "https://b.com", title="B page", tags=["work"])
        bm.add("u1", "https://c.com", title="C page")
        db.commit()
        assert len(bm.list("u1", tag="work")) == 1
        assert len(bm.list("u1", q="c page")) == 1
        bm.delete("u1", bm.list("u1")[0]["id"])
        db.commit()
        assert len(bm.list("u1")) == 1
    engine.dispose()


def test_dynamic_memory_duplicates(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="Project AURA Vision Plan", content="x"))
        db.add(Memory(id="m2", user_id="u1", title="Project AURA Vision Plan 2", content="y"))
        db.add(Memory(id="m3", user_id="u1", title="Shopping list", content="z"))
        db.commit()
        dups = DynamicMemory(db).find_duplicates("u1")
        assert len(dups) >= 1
        assert "m1" in {d["a_id"] for d in dups} | {d["b_id"] for d in dups}
    engine.dispose()


def test_dynamic_memory_merge(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="A", content="keep"))
        db.add(Memory(id="m2", user_id="u1", title="B", content="drop"))
        db.commit()
        dm = DynamicMemory(db)
        assert dm.merge("u1", "m1", "m2") is True
        db.commit()
        assert db.get(Memory, "m2") is None
        assert "drop" in db.get(Memory, "m1").content
    engine.dispose()


def test_knowledge_viz_clusters(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="Product strategy roadmap", content="strategy for the roadmap"))
        db.add(KnowledgeDocument(id="d1", user_id="u1", filename="doc.txt", storage_path="x"))
        db.flush()
        db.add(KnowledgeChunk(id="c1", document_id="d1", user_id="u1", chunk_index=0, content="engineering roadmap details"))
        db.commit()
        viz = KnowledgeVisualization(db)
        clusters = viz.topic_clusters("u1")
        kinds = {c["kind"] for c in clusters["clusters"]}
        assert "project" in kinds or "memory" in kinds or "knowledge" in kinds
        assert clusters["total"] >= 2
    engine.dispose()


def test_chunk_sentences():
    text = "First sentence here. Second sentence here. Third and final one."
    chunks = chunk_sentences(text, target_chars=25)
    assert len(chunks) >= 2
    joined = " ".join(chunks)
    assert "First" in joined


def test_chunk_with_metadata():
    chunks = chunk_with_metadata("Hello world. This is a test.", title="Doc A", source="file")
    assert chunks[0]["meta"]["title"] == "Doc A"
    assert "chunk_index" in chunks[0]["meta"]


def test_insights_detect_overdue(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Task(id="t1", user_id="u1", title="overdue task", status="todo", due_date=_now() - __import__("datetime").timedelta(days=2), created_at=_now(), updated_at=_now()))
        db.add(ActionLog(id="a1", user_id="u1", source="chat", tool="run_command", args_json="{}", result_json="{}", created_at=_now()))
        db.commit()
        ins = InsightEngine(db).insights("u1")
        assert any(i["kind"] == "overdue_tasks" for i in ins)
    engine.dispose()


def test_email_classification_rules():
    result = classify_with_rules("Invoice #1234 for your subscription", "billing@x.com", "payment due")
    assert result["kind"] == "email_bill"
    assert result["severity"] == "warning"
    assert result["matched_rule"]["kind"] == "email_bill"
