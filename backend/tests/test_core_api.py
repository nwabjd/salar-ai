# tests/test_core_api.py
import pytest

from app.services.core.brain import CoreBrain
from app.services.core.confidence import ConfidenceSystem
from app.services.core.correction import SelfCorrectionLoop
from app.services.core.events import CoreBus
from app.services.core.pipeline import CorePipeline
from app.services.core.runtime import AgentRuntime
from app.services.core.supervisor import Supervisor
from app.services.core.toolspec import ToolRegistry
from app.services.core.verification import VerificationEngine


class FakeRegistry(ToolRegistry):
    async def run(self, name, args, user_id, db_session=None, is_admin=False):
        if name == "run_command":
            cmd = str(args.get("command", ""))
            if cmd.startswith("mkdir -p "):
                return {"exit_code": 0}
            return {"exit_code": 1, "stderr": "bad"}
        if name == "code_run":
            return {"ok": True}
        return {"ok": True}


def _wire(client, sf, registry=None):
    registry = registry or FakeRegistry()
    bus = CoreBus(db_factory=sf)
    correction = SelfCorrectionLoop(registry=registry, verifier=VerificationEngine(), confidence=ConfidenceSystem(), bus=bus)
    runtime = AgentRuntime(bus=bus, correction=correction)
    brain = CoreBrain(registry=registry)
    supervisor = Supervisor(bus=bus, registry=registry)
    pipeline = CorePipeline(brain=brain, runtime=runtime, bus=bus, supervisor=supervisor, db_factory=sf, confidence=ConfidenceSystem())
    client.app.state.core_pipeline = pipeline
    client.app.state.core_runtime = runtime
    client.app.state.core_bus = bus
    client.app.state.supervisor = supervisor
    return pipeline


@pytest.fixture()
def _import_verifier():
    from app.services.core.verification import VerificationEngine
    return VerificationEngine


def test_run_happy_path(client, auth_headers, tmp_path):
    _wire(client, client.app.state.SessionLocal)
    resp = client.post("/api/core/run", json={"request": "create folder /tmp/core_test_dir"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["confidence"] >= 0.7
    assert len(data["attempted"]) >= 1
    assert len(data["verified"]) >= 1
    assert data["trace_id"]


def test_run_awaiting_approval(client, auth_headers):
    from app.services.core.brain import CorePlan, PlanStep

    class RiskyBrain(CoreBrain):
        def plan(self, intent):
            return CorePlan(
                steps=[PlanStep(id="s1", tool_name="code_run", args={"code": "rm -rf"}, description="risky step", needs_approval=True)],
                requires_approval=True,
            )

    sf = client.app.state.SessionLocal
    bus = CoreBus(db_factory=sf)
    reg = FakeRegistry()
    correction = SelfCorrectionLoop(registry=reg, verifier=VerificationEngine(), confidence=ConfidenceSystem(), bus=bus)
    runtime = AgentRuntime(bus=bus, correction=correction)
    brain = RiskyBrain(registry=reg)
    supervisor = Supervisor(bus=bus, registry=reg)
    pipeline = CorePipeline(brain=brain, runtime=runtime, bus=bus, supervisor=supervisor, db_factory=sf, confidence=ConfidenceSystem())
    client.app.state.core_pipeline = pipeline
    resp = client.post("/api/core/run", json={"request": "run bad code"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_approval"
    assert resp.json()["attempted"] == []


def test_traces_endpoint(client, auth_headers):
    _wire(client, client.app.state.SessionLocal)
    resp = client.post("/api/core/run", json={"request": "create folder /tmp/core_trace"}, headers=auth_headers)
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]
    resp2 = client.get(f"/api/core/traces/{trace_id}", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == trace_id
    assert len(resp2.json()["steps"]) >= 5


def test_list_traces(client, auth_headers):
    _wire(client, client.app.state.SessionLocal)
    client.post("/api/core/run", json={"request": "create folder /tmp/t1"}, headers=auth_headers)
    resp = client.get("/api/core/traces", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


def test_status_endpoint(client, auth_headers):
    _wire(client, client.app.state.SessionLocal)
    resp = client.get("/api/core/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "live_agents" in data
    assert "alerts" in data
    assert "bus_events_count" in data
