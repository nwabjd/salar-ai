import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Message, User
from app.services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from conftest import PREPARED_AGENT_CONTEXT


def test_conversation_and_chat_are_persisted(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Foundation"}, headers=auth_headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    reply = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "content": "What are we building?"},
        headers=auth_headers,
    )
    assert reply.status_code == 200
    assert reply.json()["assistant_message"]["content"] == "Test response to: What are we building?"

    orchestrator_call = client.app.state.agent_orchestrator.calls[0]
    with client.app.state.SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "owner@example.com"))
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "chat.completed"))
    assert orchestrator_call == {
        "prompt": "What are we building?",
        "db": orchestrator_call["db"],
        "user_id": owner.id,
        "conversation_id": conversation_id,
    }
    assert orchestrator_call["db"] is not None
    assert isinstance(orchestrator_call["db"], Session)
    assert client.app.state.coordinator.reply_calls[0]["agent_context"] == PREPARED_AGENT_CONTEXT
    assert json.loads(audit.detail_json)["agent_run_id"] == "test-agent-run-id"

    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
    assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant"]


def test_user_cannot_access_another_users_conversation(client, auth_headers):
    response = client.get("/api/conversations/not-owned", headers=auth_headers)
    assert response.status_code == 404

    chat_response = client.post(
        "/api/chat",
        json={"conversation_id": "not-owned", "content": "Do not leak this"},
        headers=auth_headers,
    )
    assert chat_response.status_code == 404
    assert client.app.state.agent_orchestrator.calls == []


def test_non_fast_stream_prepares_once_and_delivers_context_to_model(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Research"}, headers=auth_headers)
    conversation_id = created.json()["id"]

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source", "fast": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(client.app.state.agent_orchestrator.calls) == 1
    call = client.app.state.agent_orchestrator.calls[0]
    assert call["prompt"] == "Find the latest source"
    assert call["conversation_id"] == conversation_id
    assert call["user_id"]
    assert isinstance(call["db"], Session)
    system_prompt = client.app.state.coordinator.gemini.calls[0]["messages"][0]["content"]
    assert RESOURCEFUL_RESPONSE_POLICY in system_prompt
    assert PREPARED_AGENT_CONTEXT in system_prompt
    with client.app.state.SessionLocal() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "chat.completed"))
    assert json.loads(audit.detail_json)["agent_run_id"] == "test-agent-run-id"


def test_non_fast_stream_uses_coordinator_history_window(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "History"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    with client.app.state.SessionLocal() as db:
        db.add_all([
            Message(conversation_id=conversation_id, role="user", content=f"history-{index}")
            for index in range(17)
        ])
        db.commit()

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Continue", "fast": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    model_messages = client.app.state.coordinator.gemini.calls[0]["messages"]
    assert [message["content"] for message in model_messages[1:-1]] == [
        f"history-{index}" for index in range(1, 17)
    ]


def test_fast_stream_skips_prepare_but_keeps_resourceful_policy(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Voice"}, headers=auth_headers)
    conversation_id = created.json()["id"]

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Hello", "fast": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert client.app.state.agent_orchestrator.calls == []
    system_prompt = client.app.state.coordinator.gemini.calls[0]["messages"][0]["content"]
    assert RESOURCEFUL_RESPONSE_POLICY in system_prompt
    with client.app.state.SessionLocal() as db:
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "chat.completed"))
    assert "agent_run_id" not in json.loads(audit.detail_json)


def test_stream_error_does_not_record_completed_audit(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Failure"}, headers=auth_headers)
    conversation_id = created.json()["id"]
    client.app.state.coordinator.gemini.error = RuntimeError("provider unavailable")

    response = client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "content": "Find the latest source"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    with client.app.state.SessionLocal() as db:
        audits = list(db.scalars(select(AuditEvent).where(AuditEvent.action == "chat.completed")))
    assert audits == []

