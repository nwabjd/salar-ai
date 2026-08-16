# tests/test_core_brain.py
from app.services.core.brain import CoreBrain, Intent, PlanStep
from app.services.core.toolspec import ToolRegistry


def test_intent_action_create_folder():
    intent = CoreBrain().resolve_intent("create folder /tmp/hello")
    assert intent.intent_kind == "action"
    assert intent.confidence >= 0.7


def test_intent_research():
    intent = CoreBrain().resolve_intent("research the latest AI news and compare sources")
    assert intent.intent_kind == "research"
    assert intent.can_parallelize is True


def test_intent_code():
    intent = CoreBrain().resolve_intent("debug my python script")
    assert intent.intent_kind == "code"


def test_intent_chat_default():
    intent = CoreBrain().resolve_intent("how was your day?")
    assert intent.intent_kind == "chat"
    assert intent.confidence == 0.5


def test_intent_llm_fallback():
    def classifier(goal):
        return {"intent_kind": "plan", "requires_approval": True, "can_parallelize": True, "confidence": 0.8}

    brain = CoreBrain(classifier=classifier)
    intent = brain.resolve_intent("something ambiguous and novel")
    assert intent.intent_kind == "plan"
    assert intent.requires_approval is True
    assert intent.confidence == 0.8


def test_plan_action_creates_mkdir():
    brain = CoreBrain()
    intent = brain.resolve_intent("create folder /tmp/hello")
    plan = brain.plan(intent)
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool_name == "run_command"
    assert step.args["command"] == "mkdir -p /tmp/hello"
    assert step.needs_approval is False
    assert plan.requires_approval is False


def test_plan_action_url():
    brain = CoreBrain()
    intent = brain.resolve_intent("open https://example.com/about")
    plan = brain.plan(intent)
    assert plan.steps[0].tool_name == "open_url"
    assert plan.steps[0].args["url"] == "https://example.com/about"


def test_plan_action_write_file():
    brain = CoreBrain()
    intent = brain.resolve_intent("write file /tmp/note.txt with content hello world")
    plan = brain.plan(intent)
    step = plan.steps[0]
    assert step.tool_name == "file_write"
    assert step.args["path"] == "/tmp/note.txt"
    assert step.args["content"] == "hello world"


def test_plan_research_has_parallel_steps():
    brain = CoreBrain()
    intent = brain.resolve_intent("research the latest ai pricing")
    plan = brain.plan(intent)
    assert len(plan.steps) >= 2
    assert any(s.parallelizable for s in plan.steps)
    assert plan.model == "research"


def test_plan_chat_send_message():
    brain = CoreBrain()
    intent = brain.resolve_intent("how was your day?")
    plan = brain.plan(intent)
    assert plan.steps[0].tool_name == "send_message"
    assert plan.model == "chat"


def test_route():
    brain = CoreBrain()
    route = brain.route(Intent(goal="debug my python", intent_kind="code"))
    assert route["model"] == "code"
    assert "Coder" in route["agents"]
