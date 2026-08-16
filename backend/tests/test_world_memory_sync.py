# backend/tests/test_world_memory_sync.py
"""Tests for Build 2: memory unification + continuous source ingestion."""

import pytest

from app.models import (
    IntelEvent,
    KnowledgeDocument,
    MediaMemory,
    Memory,
    MemoryRelation,
)
from app.services.world_model import MemorySyncService, WorldGraph


@pytest.fixture()
def users(client):
    sf = client.app.state.SessionLocal
    with sf() as db:
        for uid in ("u1",):
            if db.get(__import__("app.models", fromlist=["User"]).User, uid) is None:
                db.add(__import__("app.models", fromlist=["User"]).User(id=uid, email=f"{uid}@example.com", password_hash="hash"))
        db.commit()


def _seed(client):
    sf = client.app.state.SessionLocal
    with sf() as db:
        db.add(Memory(id="m1", user_id="u1", title="Aurora", content="The main product", kind="project", tags_json='["product"]'))
        db.add(Memory(id="m2", user_id="u1", title="Alice", content="Leads design at Aurora", kind="person", tags_json='[]'))
        db.add(MemoryRelation(id="r1", user_id="u1", from_memory_id="m1", to_memory_id="m2", relation="member_of"))
        db.add(MediaMemory(id="mm1", user_id="u1", kind="image", caption="Aurora logo", storage_path="/tmp/logo.png"))
        db.add(KnowledgeDocument(id="k1", user_id="u1", filename="roadmap.md", full_text="Q3 launch plan", status="ready", storage_path="/tmp/roadmap.md"))
        db.add(IntelEvent(id="i1", user_id="u1", kind="email_important", severity="critical", source="email",
                          title="Server down", summary="The staging server is down"))
        db.commit()


def test_sync_memories_unifies_all_stores(client, users):
    _seed(client)
    sf = client.app.state.SessionLocal
    with sf() as db:
        counts = MemorySyncService(db).sync_all("u1")
        db.commit()
        assert counts["memories"] == 2
        assert counts["media"] == 1
        assert counts["knowledge"] == 1
        assert counts["intel"] == 1

        graph = WorldGraph(db)
        assert len(graph.entities("u1", entity_type="project")) == 1
        assert len(graph.entities("u1", entity_type="person")) == 1
        assert len(graph.entities("u1", entity_type="image")) == 1
        assert len(graph.entities("u1", entity_type="document")) == 1
        assert len(graph.entities("u1", entity_type="intel")) == 1


def test_sync_relations_mirrors_memory_graph_edges(client, users):
    _seed(client)
    sf = client.app.state.SessionLocal
    with sf() as db:
        syncer = MemorySyncService(db)
        syncer.sync_all("u1")
        syncer.sync_relations("u1")
        db.commit()

        graph = WorldGraph(db)
        project = graph._resolve("u1", "project", "aurora")
        person = graph._resolve("u1", "person", "alice")
        assert project is not None and person is not None
        neighbors = {n["relation"] for n in graph.neighbors("u1", project.id)}
        assert "member_of" in neighbors


def test_sync_is_idempotent(client, users):
    _seed(client)
    sf = client.app.state.SessionLocal
    with sf() as db:
        syncer = MemorySyncService(db)
        syncer.sync_all("u1")
        syncer.sync_all("u1")
        db.commit()
        assert len(WorldGraph(db).entities("u1", entity_type="project")) == 1
        assert len(WorldGraph(db).entities("u1", entity_type="person")) == 1


def test_memory_create_mirrors_into_world_graph(client, auth_headers):
    created = client.post("/api/memories", headers=auth_headers, json={
        "title": "Quarterly planning",
        "content": "Budget review for Q3",
    })
    assert created.status_code == 201

    snap = client.get("/api/world/snapshot", headers=auth_headers)
    assert snap.status_code == 200
    assert any(n["name"] == "Quarterly planning" for n in snap.json()["nodes"])


def test_manual_sync_endpoint(client, auth_headers):
    me = client.get("/api/auth/me", headers=auth_headers)
    uid = me.json()["id"]
    sf = client.app.state.SessionLocal
    with sf() as db:
        db.add(Memory(id="m1", user_id=uid, title="Aurora", content="The main product", kind="project", tags_json='["product"]'))
        db.add(IntelEvent(id="i1", user_id=uid, kind="email_important", severity="critical", source="email",
                          title="Server down", summary="The staging server is down"))
        db.commit()

    r = client.post("/api/world/sync", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["memories"] >= 1
    assert body["intel"] >= 1


def test_device_heartbeat_feeds_world_graph(client, auth_headers):
    device = client.post("/api/devices", headers=auth_headers, json={"name": "Studio PC", "platform": "windows"}).json()
    client.get(
        "/api/device/commands/next",
        headers={"X-Device-Token": device["token"]},
    )

    snap = client.get("/api/world/snapshot", headers=auth_headers)
    types = {n["type"] for n in snap.json()["nodes"]}
    assert "device" in types
    assert any(n["name"] == "Studio PC" for n in snap.json()["nodes"])
