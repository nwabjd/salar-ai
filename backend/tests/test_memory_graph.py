# tests/test_memory_graph.py
from app.database import Base, create_session_factory
from app.models import Memory, MemoryRelation, User
from app.services.memory_graph import MEMORY_KINDS, MemoryGraph


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mg.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.add(User(id="u2", email="u2@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _memories(sf):
    with sf() as db:
        m1 = Memory(id="m1", user_id="u1", title="AURA vision", content="...", kind="project", tags_json='["aura"]')
        m2 = Memory(id="m2", user_id="u1", title="Alice", content="...", kind="person")
        db.add_all([m1, m2])
        db.commit()


def test_kinds_constant():
    assert {"person", "project", "file", "preference", "decision", "place", "event", "memory"} <= MEMORY_KINDS


def test_connect_and_neighbors(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        g = MemoryGraph(db)
        g.connect("u1", "m1", "m2", relation="person")
        db.commit()
        nbrs = g.neighbors("u1", "m1")
        assert len(nbrs) == 1
        assert nbrs[0]["id"] == "m2"
        nbrs2 = g.neighbors("u1", "m2")
        assert nbrs2[0]["id"] == "m1"
    engine.dispose()


def test_graph_shape(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        g = MemoryGraph(db)
        g.connect("u1", "m1", "m2")
        db.commit()
        graph = g.graph("u1")
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["relation"] == "related"
    engine.dispose()


def test_memories_by_kind(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        projects = MemoryGraph(db).memories_by_kind("u1", "project")
        assert [m["id"] for m in projects] == ["m1"]
    engine.dispose()


def test_connect_self_rejected(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        import pytest
        with pytest.raises(ValueError):
            MemoryGraph(db).connect("u1", "m1", "m1")
    engine.dispose()


def test_disconnect(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        g = MemoryGraph(db)
        rel = g.connect("u1", "m1", "m2")
        db.commit()
        assert g.disconnect("u1", rel.id) is True
        db.commit()
        assert g.graph("u1")["edges"] == []
    engine.dispose()


def test_relation_model_table(tmp_path):
    engine, sf = _env(tmp_path)
    _memories(sf)
    with sf() as db:
        db.add(MemoryRelation(id="r1", user_id="u1", from_memory_id="m1", to_memory_id="m2", relation="person"))
        db.commit()
        assert db.get(MemoryRelation, "r1").relation == "person"
    engine.dispose()
