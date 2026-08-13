# tests/test_swarm.py
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
