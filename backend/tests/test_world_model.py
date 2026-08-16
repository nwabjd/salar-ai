# backend/tests/test_world_model.py
"""Tests for the World Model: WorldGraph, WorldIngestor, SituationEngine, and API."""

import pytest
from sqlalchemy import select

from app.models import User, WorldEntity, WorldRelation, WorldObservation
from app.services.world_model import SituationEngine, WorldGraph, WorldIngestor, canonical


@pytest.fixture()
def users(client):
    """Ensure u1/u2 exist so graph FKs resolve."""
    sf = client.app.state.SessionLocal
    with sf() as db:
        for uid, email in (("u1", "u1@example.com"), ("u2", "u2@example.com")):
            if db.get(User, uid) is None:
                db.add(User(id=uid, email=email, password_hash="hash"))
        db.commit()
    return {"u1": "u1", "u2": "u2"}


def test_upsert_entity_deduplicates_by_canonical_key(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", props={"repo": "aurora"}, source="test")
    graph.db.commit()
    graph.upsert_entity("u1", "project", "AURORA", name="Aurora HQ", props={"stars": 5}, source="test")
    graph.db.commit()

    entities = graph.entities("u1", entity_type="project")
    assert len(entities) == 1
    assert entities[0].name == "Aurora HQ"
    assert entities[0].props["repo"] == "aurora"
    assert entities[0].props["stars"] == 5


def test_entity_scoping_is_per_user(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.upsert_entity("u2", "project", "aurora", name="Aurora2", source="test")
    graph.db.commit()
    assert len(graph.entities("u1", entity_type="project")) == 1
    assert len(graph.entities("u2", entity_type="project")) == 1


def test_relate_creates_typed_edges(client, users):
    graph = client.app.state.world_graph_factory()
    graph.relate("u1", "person", "alice@example.com", "works_on", "project", "aurora", source="test")
    graph.db.commit()

    project = graph._resolve("u1", "project", "aurora")
    neighbors = graph.neighbors("u1", project.id)
    assert len(neighbors) == 1
    assert neighbors[0]["relation"] == "works_on"
    assert neighbors[0]["entity"]["key"] == "alice@example.com"


def test_snapshot_subgraph(client, users):
    graph = client.app.state.world_graph_factory()
    graph.relate("u1", "project", "aurora", "has_open", "file", "aurora/main.py", source="test")
    graph.db.commit()

    snap = graph.snapshot("u1", center_type="project", center_key="aurora")
    assert snap["center"]
    assert len(snap["nodes"]) >= 2
    edge_relations = {e["relation"] for e in snap["edges"]}
    assert "has_open" in edge_relations


def test_purge_expired_removes_stale_entities(client, users):
    from datetime import timedelta
    from app.models import utcnow
    graph = client.app.state.world_graph_factory()
    stale = graph.upsert_entity("u1", "device", "laptop", ttl_seconds=60, source="test")
    stale.last_seen = utcnow() - timedelta(hours=2)
    fresh = graph.upsert_entity("u1", "device", "phone", ttl_seconds=3600, source="test")
    graph.db.commit()

    removed = graph.purge_expired("u1")
    assert removed["entities"] == 1
    assert graph._resolve("u1", "device", "laptop") is None
    assert graph._resolve("u1", "device", "phone") is not None


def test_ingest_tool_observations(client, users):
    graph = client.app.state.world_graph_factory()
    ingestor = WorldIngestor(graph)
    ingestor.ingest("u1", source="tool", event_type="tool", payload={
        "tool": "open_app",
        "args": {"app": "VS Code", "path": "aurora/main.py"},
        "result": {"status": "ok"},
    })
    ingestor.ingest("u1", source="tool", event_type="tool", payload={
        "tool": "run_command",
        "args": {"command": "cargo build"},
        "result": {"exit_code": 1},
    })
    graph.db.commit()

    apps = graph.entities("u1", entity_type="app")
    assert len(apps) == 1
    files = graph.entities("u1", entity_type="file")
    assert len(files) == 1
    builds = graph.entities("u1", entity_type="build")
    assert len(builds) >= 1
    assert builds[0].props.get("status") == "failed"

    app_entity = apps[0]
    neighbors = graph.neighbors("u1", app_entity.id)
    assert any(n["relation"] == "has_open" for n in neighbors)


def test_ingest_calendar_and_device(client, users):
    graph = client.app.state.world_graph_factory()
    ingestor = WorldIngestor(graph)
    ingestor.ingest("u1", source="calendar", event_type="calendar_event", payload={
        "title": "Aurora launch review", "start": "2026-08-20T10:00:00Z",
    })
    ingestor.ingest("u1", source="device", event_type="device_heartbeat", payload={
        "name": "Studio PC", "cpu": 95, "memory": 88,
    })
    graph.db.commit()

    assert len(graph.entities("u1", entity_type="event")) == 1
    devices = graph.entities("u1", entity_type="device")
    assert len(devices) == 1
    assert devices[0].props["cpu"] == 95


def test_situation_engine_detects_deadline_and_resource_pressure(client, users):
    graph = client.app.state.world_graph_factory()
    from app.models import utcnow
    due = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    due = due + timedelta(days=1)
    graph.upsert_entity("u1", "project", "aurora", name="Aurora",
                        props={"deadline": due.isoformat()}, source="test")
    graph.upsert_entity("u1", "device", "studio-pc", name="Studio PC",
                        props={"cpu": 96, "memory": 92}, source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    situations = engine.situations("u1")
    kinds = [s["kind"] for s in situations]
    assert "deadline_pressure" in kinds
    assert "resource_pressure" in kinds
    deadline = next(s for s in situations if s["kind"] == "deadline_pressure")
    assert deadline["severity"] in ("critical", "high", "medium")


def test_situation_engine_links_failing_build_to_project(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    build = graph.upsert_entity("u1", "build", "b1", name="Aurora CI", props={"status": "failed"}, source="test")
    graph.relate("u1", "build", "b1", "of", "project", "aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    situations = engine.situations("u1")
    failing = [s for s in situations if s["kind"] == "failing_build"]
    assert failing, f"expected failing_build, got {[s['kind'] for s in situations]}"


def test_world_model_understands_what_is_happening(client, users):
    """The flagship scenario: a project with a deadline tomorrow, a failing
    build, a collaborator who just emailed, an open repo, and free resources.
    The engine must surface the deadline, the failing build, and the
    collaborator signal together — not just disconnected facts."""
    graph = client.app.state.world_graph_factory()
    from app.models import utcnow
    from datetime import timedelta
    due = (utcnow() + timedelta(days=1)).isoformat()

    graph.upsert_entity("u1", "project", "aurora", name="Aurora", props={"deadline": due}, source="test")
    build = graph.upsert_entity("u1", "build", "aurora-ci", name="Aurora CI",
                                props={"status": "failed", "exit_code": "1"}, source="test")
    graph.relate("u1", "build", "aurora-ci", "of", "project", "aurora", source="test")

    alice = graph.upsert_entity("u1", "person", "alice@example.com", name="Alice", source="test")
    email = graph.upsert_entity("u1", "email", "aurora:build is broken", name="Build is broken",
                                props={"from": "alice@example.com"}, source="test")
    email.last_seen = utcnow()
    graph.relate("u1", "email", "aurora:build is broken", "from", "person", "alice@example.com", source="test")
    graph.relate("u1", "person", "alice@example.com", "works_on", "project", "aurora", source="test")

    graph.relate("u1", "app", "vscode", "has_open", "file", "aurora/main.py", source="test")
    graph.upsert_entity("u1", "app", "vscode", name="VS Code", props={"open": True}, source="test")
    graph.relate("u1", "app", "vscode", "used_for", "project", "aurora", source="test")
    graph.upsert_entity("u1", "device", "studio-pc", name="Studio PC",
                        props={"cpu": 34, "memory": 41}, source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    situations = engine.situations("u1")
    kinds = {s["kind"] for s in situations}
    assert "deadline_pressure" in kinds, f"kinds: {kinds}"
    assert "failing_build" in kinds, f"kinds: {kinds}"
    assert "collaborator_activity" in kinds, f"kinds: {kinds}"
    assert "active_context" in kinds, f"kinds: {kinds}"
    assert "resource_pressure" not in kinds  # resources are fine — no false alarm
    by_kind = {s["kind"]: s for s in situations}
    assert by_kind["deadline_pressure"]["props"]["days_left"] <= 3
    assert by_kind["collaborator_activity"]["title"].startswith("Alice")


def test_world_api_observe_and_snapshot(client, auth_headers):
    observed = client.post("/api/world/observe", headers=auth_headers, json={
        "source": "tool",
        "event_type": "tool",
        "payload": {"tool": "open_app", "args": {"app": "VS Code", "path": "aurora/main.py"}, "result": {}},
    })
    assert observed.status_code == 200
    assert observed.json()["event_type"] == "tool"

    snap = client.get("/api/world/snapshot", headers=auth_headers)
    assert snap.status_code == 200
    assert snap.json()["nodes"]

    situations = client.get("/api/world/situations", headers=auth_headers)
    assert situations.status_code == 200
    assert isinstance(situations.json(), list)


def test_world_api_entity_and_relation_crud(client, auth_headers):
    created = client.post("/api/world/entities", headers=auth_headers, json={
        "entity_type": "project", "key": "aurora", "name": "Aurora", "props": {"repo": "aurora"},
    })
    assert created.status_code == 200
    assert created.json()["key"] == "aurora"

    related = client.post("/api/world/relations", headers=auth_headers, json={
        "from_type": "project", "from_key": "aurora", "relation": "uses",
        "to_type": "app", "to_key": "vscode",
    })
    assert related.status_code == 200

    searched = client.get("/api/world/search", headers=auth_headers, params={"q": "aurora"})
    assert searched.status_code == 200
    assert len(searched.json()) == 1


def test_canonical_normalization():
    assert canonical("project", "Aurora") == "project:aurora"
    assert canonical("person", "alice@example.com") == "person:alice@example.com"
    assert canonical("project", "") == ""


def test_situation_context_text_summarizes_active_state(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", props={"deadline": "2099-01-01T00:00:00"}, source="test")
    build = graph.upsert_entity("u1", "build", "aurora-ci", name="Aurora CI",
                                props={"status": "failed", "exit_code": "1"}, source="test")
    graph.relate("u1", "build", "aurora-ci", "of", "project", "aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    text = engine.context_text("u1")
    assert "latest build is failing" in text
    assert "Aurora" in text


def test_situation_context_text_empty_when_nothing_happening(client, users):
    graph = client.app.state.world_graph_factory()
    graph.db.commit()
    engine = SituationEngine(graph)
    assert engine.context_text("u1") == ""


def test_coordinator_payload_includes_situations_block(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    build = graph.upsert_entity("u1", "build", "aurora-ci", name="Aurora CI",
                                props={"status": "failed"}, source="test")
    graph.relate("u1", "build", "aurora-ci", "of", "project", "aurora", source="test")
    graph.db.commit()

    coordinator = client.app.state.coordinator
    payload = coordinator.build_payload(
        prompt="how is everything going?",
        messages=[],
        memories=[],
        documents=[],
        situations_context=_situations_for(client, "u1"),
    )
    system = payload[0]["content"]
    assert "What is happening right now" in system
    assert "latest build is failing" in system
    assert "mention it proactively" in system


def test_projected_outcomes_forecasts_untouched_state(client, users):
    from datetime import timedelta
    from app.models import utcnow
    graph = client.app.state.world_graph_factory()
    due = (utcnow() + timedelta(hours=12)).isoformat()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora",
                        props={"deadline": due}, source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    projection = engine.projected_outcomes("u1")
    assert "deadline" in projection
    assert "untouched" in projection
    assert "hours" in projection or "days" in projection


def test_projected_outcomes_empty_when_nothing_happening(client, users):
    graph = client.app.state.world_graph_factory()
    graph.db.commit()
    engine = SituationEngine(graph)
    assert engine.projected_outcomes("u1") == ""


def _situations_for(client, user_id: str) -> str:
    from app.services.world_model import SituationEngine, WorldGraph
    with client.app.state.SessionLocal() as db:
        return SituationEngine(WorldGraph(db)).context_text(user_id)
