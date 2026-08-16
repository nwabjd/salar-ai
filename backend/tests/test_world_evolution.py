"""Tests for Self-Evolution: EvolutionEngine and world policy endpoints."""
import pytest
from app.models import User
from app.services.world_model import (
    EvolutionEngine,
    SituationActionPlanner,
)


@pytest.fixture()
def users(client):
    sf = client.app.state.SessionLocal
    with sf() as db:
        for uid, email in (("u1", "u1@example.com"), ("u2", "u2@example.com")):
            if db.get(User, uid) is None:
                db.add(User(id=uid, email=email, password_hash="hash"))
        db.commit()
    return {"u1": "u1", "u2": "u2"}


def test_record_and_evolve_learns_successful_action(client, users):
    with client.app.state.SessionLocal() as db:
        engine = EvolutionEngine(db)
        for _ in range(3):
            engine.record_execution(
                "u1", "failing_build", "Investigate build failure",
                outcome="success", resolved=True,
            )
        engine.record_execution(
            "u1", "failing_build", "Rebuild from scratch",
            outcome="failure", resolved=False,
        )
        policies = engine.evolve("u1")
        db.flush()

    by_title = {p["action_title"]: p for p in policies}
    investigate = by_title["Investigate build failure"]
    rebuild = by_title["Rebuild from scratch"]

    assert investigate["attempts"] == 3
    assert investigate["successes"] == 3
    assert investigate["resolved_count"] == 3
    assert investigate["score"] > 0.9

    assert rebuild["attempts"] == 1
    assert rebuild["successes"] == 0
    assert rebuild["score"] < investigate["score"]


def test_evolve_isolates_per_user(client, users):
    with client.app.state.SessionLocal() as db:
        engine = EvolutionEngine(db)
        engine.record_execution(
            "u1", "failing_build", "Investigate build failure",
            outcome="success", resolved=True,
        )
        engine.record_execution(
            "u2", "failing_build", "Rebuild from scratch",
            outcome="failure", resolved=False,
        )
        policies_u1 = engine.evolve("u1")
        db.flush()

    titles_u1 = {p["action_title"] for p in policies_u1}
    assert "Investigate build failure" in titles_u1
    assert "Rebuild from scratch" not in titles_u1


def test_planner_attaches_learned_score(client, users):
    with client.app.state.SessionLocal() as db:
        engine = EvolutionEngine(db)
        engine.record_execution(
            "u1", "failing_build", "Investigate build failure",
            outcome="success", resolved=True,
        )
        engine.record_execution(
            "u1", "failing_build", "Investigate build failure",
            outcome="success", resolved=True,
        )
        engine.evolve("u1")
        db.flush()

        from app.services.world_model import WorldGraph, SituationEngine
        graph = WorldGraph(db)
        graph.upsert_entity("u1", "project", "aurora", name="Aurora", source="test")
        graph.upsert_entity("u1", "build", "aurora-ci", name="Aurora CI",
                            props={"status": "failed"}, source="test")
        graph.relate("u1", "build", "aurora-ci", "of", "project", "aurora", source="test")
        db.flush()

        situations = SituationEngine(graph).situations("u1")
        actions = SituationActionPlanner(db).propose_actions("u1", situations)
        failing = [a for a in actions if a["situation_kind"] == "failing_build"]
        assert len(failing) >= 1
        assert failing[0]["score"] > 0.0
        assert failing[0]["risk"] == "high"


def test_policies_endpoint(client, users):
    def auth_headers():
        from conftest import make_supabase_token
        token = make_supabase_token(client.app.state.settings, email="owner@example.com")
        resp = client.post("/api/auth/supabase", json={"token": token})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    uid = client.get("/api/auth/me", headers=auth_headers()).json()["id"]

    with client.app.state.SessionLocal() as db:
        engine = EvolutionEngine(db)
        engine.record_execution(uid, "failing_build", "Investigate build failure",
                                outcome="success", resolved=True)
        db.commit()

    resp = client.post("/api/world/evolve", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert any(p["action_title"] == "Investigate build failure" for p in resp.json()["policies"])

    resp = client.get("/api/world/policies", headers=auth_headers())
    assert resp.status_code == 200
    assert any(p["action_title"] == "Investigate build failure" for p in resp.json())


def test_execute_action_endpoint_records_execution(client, users):
    def auth_headers():
        from conftest import make_supabase_token
        token = make_supabase_token(client.app.state.settings, email="owner@example.com")
        resp = client.post("/api/auth/supabase", json={"token": token})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    uid = client.get("/api/auth/me", headers=auth_headers()).json()["id"]

    resp = client.post("/api/world/actions/execute", headers=auth_headers(), json={
        "situation_kind": "failing_build",
        "action_title": "Investigate build failure",
        "tool_calls": [{"name": "get_current_time", "args": {}}],
        "risk": "low",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "success"
    assert data["results"][0]["tool"] == "get_current_time"

    resp = client.post("/api/world/evolve", headers=auth_headers())
    assert any(p["action_title"] == "Investigate build failure" and p["attempts"] >= 1
               for p in resp.json()["policies"])


def test_execute_action_high_risk_requires_confirmation(client, users):
    def auth_headers():
        from conftest import make_supabase_token
        token = make_supabase_token(client.app.state.settings, email="owner@example.com")
        resp = client.post("/api/auth/supabase", json={"token": token})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post("/api/world/actions/execute", headers=auth_headers(), json={
        "situation_kind": "failing_build",
        "action_title": "Run shell fix",
        "tool_calls": [{"name": "run_command", "args": {"command": "rm -rf /tmp/x"}}],
        "risk": "high",
        "confirmed": False,
    })
    assert resp.status_code == 428
