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


def _session_has_chat_audit(session, action):
    tracked = list(session.new) + list(session.identity_map.values())
    if any(isinstance(instance, AuditEvent) and instance.action == action for instance in tracked):
        return True
    return session.scalar(select(AuditEvent.id).where(AuditEvent.action == action).limit(1)) is not None


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


def test_standard_chat_ambiguous_commit_returns_persisted_success(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Atomic ambiguity"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    raised = False

    def persist_completion_then_raise(session):
        nonlocal raised
        if not raised and _session_has_chat_audit(session, "chat.completed"):
            raised = True
            original_commit(session)
            raise RuntimeError("commit acknowledgement lost")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", persist_completion_then_raise)
    response = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "completed")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["chat.completed"]


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


def test_stream_setup_commit_failure_leaves_no_completed_run(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Setup failed"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit

    def fail_user_setup_commit(session):
        if any(isinstance(instance, Message) and instance.role == "user" for instance in session.new):
            raise RuntimeError("setup commit failed")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_user_setup_commit)
    with pytest.raises(RuntimeError, match="setup commit failed"):
        client.post(
            "/api/chat/stream",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )

    with client.app.state.SessionLocal() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.conversation_id == conversation_id))
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert run is None
    assert messages == []
    assert not any(audit.action == "chat.completed" for audit in audits)


def test_stream_ambiguous_setup_commit_continues_once(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Setup ambiguity"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    raised = False

    def persist_user_setup_then_raise(session):
        nonlocal raised
        if not raised and any(isinstance(instance, Message) and instance.role == "user" for instance in session.new):
            raised = True
            original_commit(session)
            raise RuntimeError("setup acknowledgement lost")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", persist_user_setup_then_raise)
    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.text.count('"type": "done"') == 1
    assert '"type": "error"' not in response.text
    assert len(client.app.state.coordinator.gemini.calls) == 1
    with client.app.state.SessionLocal() as db:
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["chat.completed"]


def test_stream_ambiguous_setup_cancellation_reconciles_cancelled(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Setup cancelled"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    raised = False

    def persist_user_setup_then_cancel(session):
        nonlocal raised
        if not raised and any(isinstance(instance, Message) and instance.role == "user" for instance in session.new):
            raised = True
            original_commit(session)
            raise asyncio.CancelledError()
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", persist_user_setup_then_cancel)
    with pytest.raises(FutureCancelledError):
        client.post(
            "/api/chat/stream",
            json={"conversation_id": conversation_id, "content": "Find the latest source"},
            headers=auth_headers,
        )

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = _chat_audits(db, conversation_id)
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "cancelled")
    assert [audit.action for audit in audits] == ["chat.cancelled"]


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
        committing_completion = _session_has_chat_audit(session, "chat.completed")
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


def test_stream_ambiguous_completion_commit_emits_done_without_false_failure(client, auth_headers, monkeypatch):
    created = client.post("/api/conversations", json={"title": "Completion ambiguity"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.agent_orchestrator = AgentOrchestrator(research=SuccessfulResearch())
    original_commit = Session.commit
    raised = False

    def persist_completion_then_raise(session):
        nonlocal raised
        if not raised and _session_has_chat_audit(session, "chat.completed"):
            raised = True
            original_commit(session)
            raise RuntimeError("completion acknowledgement lost")
        return original_commit(session)

    monkeypatch.setattr(Session, "commit", persist_completion_then_raise)
    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.text.count('"type": "done"') == 1
    assert '"type": "error"' not in response.text
    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        messages = list(db.scalars(select(Message).where(Message.conversation_id == conversation_id)))
        audits = _chat_audits(db, conversation_id)
    assert run.status == "completed"
    assert [(step.name, step.status) for step in steps][-1] == ("chat", "completed")
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [audit.action for audit in audits] == ["chat.completed"]


def test_terminal_audit_primary_key_makes_competing_outcomes_idempotent(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Terminal race"}, headers=auth_headers)
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

    outcomes = [
        ("chat.cancelled", "cancelled"),
        ("chat.failed", "failed"),
        ("chat.completed", "completed"),
    ]
    observed = [
        _reconcile_chat_terminal(
            client.app.state.SessionLocal,
            terminal_event_id=terminal_event_id,
            user_id=user_id,
            conversation_id=conversation_id,
            prompt="Find the latest source",
            action=action,
            status=outcome_status,
            reason="Competing terminal outcome.",
            agent_run_id=run_id,
        )
        for action, outcome_status in outcomes
    ]

    with client.app.state.SessionLocal() as db:
        run, steps = _run_and_steps(db, conversation_id)
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.id == terminal_event_id)))
    assert observed == ["chat.cancelled"] * 3
    assert run.status == "cancelled"
    assert [(step.name, step.status) for step in steps] == [("chat", "cancelled")]
    assert [audit.action for audit in audits] == ["chat.cancelled"]


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
        if _session_has_chat_audit(session, "chat.completed"):
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
    assert commit_calls == 3
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
