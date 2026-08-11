import asyncio
import json
from concurrent.futures import CancelledError as FutureCancelledError

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.chat import _reconcile_chat_terminal
from app.models import AgentRun, AgentRunStep, AuditEvent, Message, token_id
from app.services.agents.contracts import AgentResult, EvidenceSource
from app.services.agents.orchestrator import AgentOrchestrator


class SuccessfulResearch:
    async def run(self, query):
        return AgentResult(
            status="completed",
            summary="Verified current source.",
            confidence="high",
            evidence=[EvidenceSource(
                title="Source",
                url="https://research.example/source",
                excerpt_summary="Verified evidence.",
                publisher="Example",
                confidence="high",
                evidence_kind="opened_page",
            )],
        )


class CancelledResearch:
    async def run(self, query):
        raise asyncio.CancelledError()


class ToolLoopGemini:
    def __init__(self):
        self.calls = []

    async def chat_with_tools(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        return {
            "text": "",
            "function_calls": [{"name": "list_devices", "args": {}}],
            "finish_reason": "STOP",
        }


def _agent_audits(db, conversation_id):
    return list(db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.action.like("agent.%"),
            AuditEvent.detail_json.contains(conversation_id),
        )
        .order_by(AuditEvent.created_at)
    ))


def _run_and_steps(db, conversation_id):
    run = db.scalar(select(AgentRun).where(AgentRun.conversation_id == conversation_id))
    steps = list(db.scalars(
        select(AgentRunStep)
        .where(AgentRunStep.run_id == run.id)
        .order_by(AgentRunStep.sequence)
    ))
    return run, steps


def _session_has_agent_audit(session, action):
    tracked = list(session.new) + list(session.identity_map.values())
    if any(isinstance(instance, AuditEvent) and instance.action == action for instance in tracked):
        return True
    return session.scalar(select(AuditEvent.id).where(AuditEvent.action == action).limit(1)) is not None


def test_agent_gemini_failure_persists_failed_terminal_outcome(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Agent failure"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    client.app.state.coordinator.gemini.error = RuntimeError("provider-secret")

    with pytest.raises(RuntimeError, match="Agent processing failed") as raised:
        client.post(
            "/api/agent",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )
    assert "provider-secret" not in str(raised.value)

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _agent_audits(db, conversation_id)
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "failed")
    assert messages == []
    assert [audit.action for audit in audits] == ["agent.failed"]
    assert "provider-secret" not in audits[0].detail_json


def test_agent_refresh_failure_rolls_back_messages_and_persists_failure(
    client,
    auth_headers,
    monkeypatch,
):
    created = client.post("/api/conversations", json={"title": "Agent refresh failure"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_refresh = Session.refresh

    def fail_assistant_refresh(session, instance, *args, **kwargs):
        if isinstance(instance, Message) and instance.role == "assistant":
            raise RuntimeError("refresh-secret")
        return original_refresh(session, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "refresh", fail_assistant_refresh)
    with pytest.raises(RuntimeError, match="Agent processing failed") as raised:
        client.post(
            "/api/agent",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )
    assert "refresh-secret" not in str(raised.value)

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _agent_audits(db, conversation_id)
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "failed")
    assert messages == []
    assert [audit.action for audit in audits] == ["agent.failed"]
    assert "refresh-secret" not in audits[0].detail_json


def test_agent_cancellation_persists_cancelled_terminal_outcome(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Agent cancelled"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    client.app.state.coordinator.gemini.error = asyncio.CancelledError()

    with pytest.raises(FutureCancelledError):
        client.post(
            "/api/agent",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _agent_audits(db, conversation_id)
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "cancelled")
    assert [audit.action for audit in audits] == ["agent.cancelled"]


def test_agent_prepare_cancellation_adds_explicit_agent_terminal_step(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Prepare cancelled"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=CancelledResearch())

    with pytest.raises(FutureCancelledError):
        client.post(
            "/api/agent",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _agent_audits(db, conversation_id)
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "cancelled")
    assert [audit.action for audit in audits] == ["agent.cancelled"]


def test_agent_ambiguous_success_commit_returns_once_without_false_failure(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Agent ambiguity"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    raised = False

    def persist_completion_then_raise(session):
        nonlocal raised
        if not raised and _session_has_agent_audit(session, "agent.completed"):
            raised = True
            original_commit(session)
            raise RuntimeError("agent commit acknowledgement lost")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", persist_completion_then_raise)
    response = client.post(
        "/api/agent",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "Test streamed response"
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _agent_audits(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "completed")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["agent.completed"]


def test_agent_terminal_primary_key_keeps_first_competing_outcome(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Agent race"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    user_id = client.get("/api/auth/me", headers=auth_headers).json()["id"]
    terminal_event_id = token_id()
    with client.app.state.SessionLocal() as db:
        run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            kind="research",
            status="completed",
        )
        db.add(run)
        db.commit()
        run_id = run.id

    outcomes = [("agent.cancelled", "cancelled"), ("agent.failed", "failed"), ("agent.completed", "completed")]
    observed = [
        _reconcile_chat_terminal(
            client.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt="Find the latest source",
            action=action,
            status=status,
            reason="Competing agent outcome.",
            agent_run_id=run_id,
            outcome_name="agent",
        )
        for action, status in outcomes
    ]

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.id == terminal_event_id)))
    assert observed == ["agent.cancelled"] * 3
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps] == [("agent", "cancelled")]
    assert [audit.action for audit in audits] == ["agent.cancelled"]


def test_agent_tool_loop_exhaustion_persists_truthful_partial_response(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Agent partial"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    client.app.state.coordinator.gemini = ToolLoopGemini()

    async def fake_execute_tool(name, args, user_id, db, is_admin=False):
        return {"devices": [], "count": 0}

    monkeypatch.setattr("app.api.agent.execute_tool", fake_execute_tool)
    response = client.post(
        "/api/agent",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_message"]["id"]
    assert body["assistant_message"]["id"]
    assert "processing limit" in body["assistant_message"]["content"]
    assert len(body["tools_used"]) == 5
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _agent_audits(db, conversation_id)
    assert run.status == "partial"
    assert [(step.name, step.status) for step in steps][-1] == ("agent", "partial")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["agent.partial"]
    detail = json.loads(audits[0].detail_json)
    assert detail["tools"] == ["list_devices"] * 5
