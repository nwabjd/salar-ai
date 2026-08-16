"""Tests for World Model Build 4 (action planner) and Simulation Engine."""
import pytest
from app.models import User
from app.services.world_model import (
    ActionPlan,
    SituationActionPlanner,
    SituationEngine,
    WorldGraph,
    WorldSimulator,
)


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


def _auth_headers(client, email="owner@example.com"):
    from conftest import make_supabase_token
    token = make_supabase_token(client.app.state.settings, email=email)
    resp = client.post("/api/auth/supabase", json={"token": token})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _near_deadline(days=1):
    from datetime import timedelta
    from app.models import utcnow
    return (utcnow() + timedelta(days=days)).isoformat()


def _auth_user_id(client):
    resp = client.get("/api/auth/me", headers=_auth_headers(client))
    return resp.json()["id"]


def test_action_planner_proposes_investigate_for_failing_build(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.upsert_entity("u1", "build", "aurora-ci", name="Aurora CI",
                        props={"status": "failed"}, source="test")
    graph.relate("u1", "build", "aurora-ci", "of", "project", "aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    situations = engine.situations("u1")
    planner = SituationActionPlanner(graph.db)
    actions = planner.propose_actions("u1", situations)

    failing = [a for a in actions if a["situation_kind"] == "failing_build"]
    assert len(failing) >= 1
    assert "git status" in failing[0]["tool_calls"][0]["args"]["command"]


def test_action_planner_proposes_reply_for_collaborator(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.upsert_entity("u1", "person", "alice@example.com", name="Alice", source="test")
    email = graph.upsert_entity("u1", "email", "aurora:build is broken", name="Build is broken",
                                props={"from": "alice@example.com"}, source="test")
    from app.models import utcnow
    email.last_seen = utcnow()
    graph.relate("u1", "email", "aurora:build is broken", "from", "person", "alice@example.com", source="test")
    graph.relate("u1", "person", "alice@example.com", "works_on", "project", "aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    situations = engine.situations("u1")
    planner = SituationActionPlanner(graph.db)
    actions = planner.propose_actions("u1", situations)

    collab = [a for a in actions if a["situation_kind"] == "collaborator_activity"]
    assert len(collab) >= 1
    assert "Email" in collab[0]["title"]


def test_action_planner_empty_when_no_situations(client, users):
    graph = client.app.state.world_graph_factory()
    graph.db.commit()
    planner = SituationActionPlanner(graph.db)
    actions = planner.propose_actions("u1", [])
    assert actions == []


def test_action_plan_to_dict():
    plan = ActionPlan(
        situation_kind="test",
        title="Test Action",
        description="Does something",
        tool_calls=[{"name": "run_command", "args": {"command": "ls"}}],
        severity="high",
    )
    d = plan.to_dict()
    assert d["situation_kind"] == "test"
    assert d["severity"] == "high"
    assert len(d["tool_calls"]) == 1


def test_api_actions_endpoint(client, users):
    uid = _auth_user_id(client)
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity(uid, "project", "aurora", name="Aurora", source="test")
    graph.upsert_entity(uid, "build", "aurora-ci", name="Aurora CI",
                        props={"status": "failed"}, source="test")
    graph.relate(uid, "build", "aurora-ci", "of", "project", "aurora", source="test")
    graph.db.commit()

    resp = client.get("/api/world/actions", headers=_auth_headers(client))
    assert resp.status_code == 200
    actions = resp.json()
    assert isinstance(actions, list)
    assert any(a["situation_kind"] == "failing_build" for a in actions)


# ---- Simulation Engine tests ----


def test_simulator_detects_new_situation(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    before = engine.situations("u1")
    simulator = WorldSimulator(graph, engine)

    result = simulator.simulate("u1", [{
        "action": "set_entity_prop",
        "params": {"entity_type": "project", "key": "aurora", "prop": "deadline", "value": _near_deadline()},
    }])

    assert result.scenarios_before == before
    new_kinds = [c.kind for c in result.consequences if c.delta == "new"]
    assert "deadline_pressure" in new_kinds
    assert "deadline_pressure" in result.narrative
    assert "CREATE" in result.narrative


def test_simulator_rollback_leaves_graph_unchanged(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    simulator = WorldSimulator(graph, engine)

    result = simulator.simulate("u1", [{
        "action": "set_entity_prop",
        "params": {"entity_type": "project", "key": "aurora", "prop": "deadline", "value": _near_deadline()},
    }])
    assert len(result.consequences) > 0

    engine2 = SituationEngine(graph)
    after = engine2.situations("u1")
    kinds = [s["kind"] for s in after]
    assert "deadline_pressure" not in kinds


def test_simulator_no_change_returns_empty(client, users):
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.db.commit()

    engine = SituationEngine(graph)
    simulator = WorldSimulator(graph, engine)

    result = simulator.simulate("u1", [])
    assert result.consequences == []
    assert "No significant" in result.narrative


def test_simulate_api_endpoint(client, users):
    uid = _auth_user_id(client)
    graph = client.app.state.world_graph_factory()
    graph.upsert_entity(uid, "project", "aurora", name="Aurora", source="test")
    graph.db.commit()

    resp = client.post("/api/world/simulate", headers=_auth_headers(client), json={
        "changes": [{
            "action": "set_entity_prop",
            "params": {"entity_type": "project", "key": "aurora", "prop": "deadline", "value": _near_deadline()},
        }]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "consequences" in data
    assert "narrative" in data
    assert any(c["delta"] == "new" for c in data["consequences"])


def test_world_simulate_tool(client, users):
    import asyncio
    from app.services.agent import execute_tool

    graph = client.app.state.world_graph_factory()
    graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
    graph.db.commit()

    with client.app.state.SessionLocal() as db:
        result = asyncio.run(execute_tool(
            "world_simulate",
            {"changes": [{
                "action": "set_entity_prop",
                "params": {"entity_type": "project", "key": "aurora", "prop": "deadline", "value": _near_deadline()},
            }]},
            "u1",
            db,
        ))
    assert "consequences" in result
    assert any(c["delta"] == "new" for c in result["consequences"])


def test_world_simulate_tool_errors_on_empty_changes(client, users):
    import asyncio
    from app.services.agent import execute_tool

    with client.app.state.SessionLocal() as db:
        result = asyncio.run(execute_tool("world_simulate", {"changes": []}, "u1", db))
    assert "error" in result
