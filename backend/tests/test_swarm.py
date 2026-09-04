# tests/test_swarm.py
import asyncio
from copy import deepcopy

from app.database import Base, create_session_factory
from app.models import AgentRun, AgentRunStep, User
from app.services.swarm import AgentSwarm


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'swarm.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_decompose_picks_relevant_agents(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        swarm = AgentSwarm(db)
        agents = swarm.decompose("research the best camera and organize my downloads")
        names = {a["name"] for a in agents}
        assert "Researcher" in names
        assert "File Manager" in names
        assert len(agents) >= 2
    engine.dispose()


def test_decompose_defaults(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        agents = AgentSwarm(db).decompose("hello")
        names = [a["name"] for a in agents]
        assert "Researcher" in names
        assert "System" in names
    engine.dispose()


def test_create_run_records_steps(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        swarm = AgentSwarm(db)
        agents = swarm.decompose("write code to parse invoices")
        run = swarm.create_run("u1", "write code to parse invoices", agents)
        db.commit()
        assert run.kind == "swarm"
        steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).all()
        assert len(steps) == len(agents)
        summary = swarm.agent_summary(run)
        assert summary["input"]["goal"] == "write code to parse invoices"
        assert len(summary["agents"]) == len(agents)
    engine.dispose()


def test_create_run_coder_agent(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        agents = AgentSwarm(db).decompose("build a python script")
        assert any(a["name"] == "Coder" for a in agents)
    engine.dispose()


class _ToolGemini:
    """Fake gemini that issues one real tool call (get_current_time) then stops."""

    def __init__(self):
        self.calls = 0

    async def chat_with_tools(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return {
                "text": "",
                "function_calls": [{"name": "get_current_time", "args": {}}],
                "finish_reason": "",
            }
        return {"text": "The current time was retrieved.", "function_calls": [], "finish_reason": "STOP"}


class _Coordinator:
    def __init__(self):
        self.gemini = _ToolGemini()


def test_run_executes_real_tool_and_persists_result(tmp_path):
    engine, sf = _env(tmp_path)

    async def _go():
        with sf() as db:
            coordinator = _Coordinator()
            swarm = AgentSwarm(db, coordinator=coordinator, user_id="u1", is_admin=False,
                                base_url="http://test", jwt_secret="secret", db_session=db,
                                max_tool_rounds=2)
            agents = [{"name": "System", "description": "System monitor", "tools": ["get_system_info", "get_uptime", "get_current_time"]}]
            run = swarm.create_run("u1", "check the time", agents)
            db.commit()
            out = await swarm.execute_swarm(run)
            return run, out

    run, out = asyncio.run(_go())
    with sf() as db:
        steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run.id).all()
        assert steps
        detail = steps[0].detail_json
        import json
        parsed = json.loads(detail)
        assert "tool_calls" in parsed
        tool_names = [t["tool"] for t in parsed["tool_calls"]]
        assert "get_current_time" in tool_names
        assert "datetime" in str(parsed["tool_calls"])
    engine.dispose()


def test_run_without_coordinator_gracefully_noops(tmp_path):
    engine, sf = _env(tmp_path)

    async def _go():
        with sf() as db:
            swarm = AgentSwarm(db, user_id="u1", db_session=db, max_tool_rounds=1)
            agents = [{"name": "System", "description": "System monitor", "tools": ["get_uptime"]}]
            run = swarm.create_run("u1", "check status", agents)
            db.commit()
            out = await swarm.execute_swarm(run)
            return run, out

    run, out = asyncio.run(_go())
    assert out["status"] == "completed"
    engine.dispose()
