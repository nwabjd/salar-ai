import asyncio
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentRun, AgentRunStep, AuditEvent, Message
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


def _chat_audits(db, conversation_id):
    return list(db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.action.like("chat.%"),
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


def test_standard_chat_commits_run_messages_and_audit_once(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Atomic"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    commit_calls = 0

    def count_commit(session):
        nonlocal commit_calls
        commit_calls += 1
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", count_commit)
    response = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert commit_calls == 1
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "completed")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["chat.completed"]


def test_standard_chat_outer_commit_failure_reconciles_failed_run(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Atomic failure"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    commit_calls = 0

    def fail_first_commit(session):
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            raise RuntimeError("outer chat commit failed")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_first_commit)
    with pytest.raises(RuntimeError, match="outer chat commit failed"):
        client.post(
            "/api/chat",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert commit_calls == 2
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "failed")
    assert messages == []
    assert [audit.action for audit in audits] == ["chat.failed"]


def test_stream_success_appends_completed_chat_outcome(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Stream success"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "completed")


def test_stream_refresh_failure_rolls_back_completed_outcome(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Refresh failed"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_refresh = Session.refresh

    def fail_assistant_refresh(session, instance, *args, **kwargs):
        if isinstance(instance, Message) and instance.role == "assistant":
            raise RuntimeError("assistant refresh failed")
        return original_refresh(session, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "refresh", fail_assistant_refresh)
    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    assert '"type": "done"' not in response.text
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "failed")
    assert [message.role for message in messages] == ["user"]
    assert [audit.action for audit in audits] == ["chat.failed"]


def test_stream_has_no_fallible_database_work_after_completed_commit(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Post commit"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    original_refresh = Session.refresh

    def mark_completed_commit(session):
        committing_completion = any(
            isinstance(instance, AuditEvent) and instance.action == "chat.completed"
            for instance in session.new
        )
        result = original_commit(session)
        if committing_completion:
            session.info["chat_completed_committed"] = True
        return result

    def reject_post_commit_refresh(session, instance, *args, **kwargs):
        if session.info.get("chat_completed_committed"):
            raise RuntimeError("database access after completed commit")
        return original_refresh(session, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "commit", mark_completed_commit)
    monkeypatch.setattr(Session, "refresh", reject_post_commit_refresh)
    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert '"type": "error"' not in response.text
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _chat_audits(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "completed")
    assert [audit.action for audit in audits] == ["chat.completed"]


def test_stream_failure_reconciles_completed_research_run(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Stream failed"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    client.app.state.coordinator.gemini.error = RuntimeError("provider secret")

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "failed")


def test_stream_assistant_commit_failure_keeps_user_and_reconciles_run(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Stream commit failed"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    commit_calls = 0

    def fail_assistant_commit(session):
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 5:
            raise RuntimeError("assistant commit failed")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_assistant_commit)
    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert '"type": "error"' in response.text
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert commit_calls == 6
    assert run.status == "failed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "failed")
    assert [message.role for message in messages] == ["user"]
    assert [audit.action for audit in audits] == ["chat.failed"]


def test_direct_asgi_disconnect_records_cancelled_and_reconciles_run(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Disconnected"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    body = json.dumps({
        "conversation_id": conversation_id,
        "content": "Find the latest source",
    }).encode()
    request_messages = iter([
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ])
    async def receive():
        return next(request_messages)

    async def send(message):
        if message["type"] == "http.response.body" and message.get("more_body"):
            await asyncio.Event().wait()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/chat/stream",
        "raw_path": b"/api/chat/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"authorization", auth_headers["Authorization"].encode()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }

    asyncio.run(client.app(scope, receive, send))

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _chat_audits(db, conversation_id)
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "cancelled")
    assert [audit.action for audit in audits] == ["chat.cancelled"]


def test_asgi_24_send_disconnect_records_cancelled_and_reconciles_run(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Send disconnected"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    body = json.dumps({
        "conversation_id": conversation_id,
        "content": "Find the latest source",
    }).encode()
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Event().wait()

    async def send(message):
        if message["type"] == "http.response.body" and message.get("more_body"):
            raise OSError("client disconnected")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/chat/stream",
        "raw_path": b"/api/chat/stream",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"authorization", auth_headers["Authorization"].encode()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }

    asyncio.run(client.app(scope, receive, send))

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _chat_audits(db, conversation_id)
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "cancelled")
    assert [audit.action for audit in audits] == ["chat.cancelled"]
