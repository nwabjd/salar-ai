# backend/tests/test_swarm_execution.py
import pytest


def test_swarm_agents_list(client, auth_headers):
    resp = client.get("/api/swarm/agents", headers=auth_headers)
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert len(agents) >= 8
    names = [a["name"] for a in agents]
    assert "Researcher" in names
    assert "Architect" in names
    assert "Analyst" in names
    assert "Security" in names


def test_swarm_decompose_and_execution(client, auth_headers):
    # 1. Decompose a complex goal
    goal = "Audit database security, analyze metrics, and refactor Python code"
    dec_resp = client.post("/api/swarm/decompose", headers=auth_headers, json={"goal": goal})
    assert dec_resp.status_code == 200
    chosen = [a["name"] for a in dec_resp.json()["agents"]]
    assert "Security" in chosen or "Coder" in chosen or "Analyst" in chosen

    # 2. Run swarm in parallel
    run_resp = client.post("/api/swarm/run", headers=auth_headers, json={"goal": goal})
    assert run_resp.status_code == 200
    run_data = run_resp.json()["run"]
    assert run_data["status"] == "completed"
    assert "agents" in run_data
    assert len(run_data["agents"]) >= 2
    assert "output" in run_data
    assert "blackboard" in run_data["output"]

    # 3. Get run by id
    get_resp = client.get(f"/api/swarm/runs/{run_data['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["run"]["id"] == run_data["id"]

    # 4. List recent runs
    list_resp = client.get("/api/swarm/runs", headers=auth_headers)
    assert list_resp.status_code == 200
    runs = list_resp.json()["runs"]
    assert any(r["id"] == run_data["id"] for r in runs)
