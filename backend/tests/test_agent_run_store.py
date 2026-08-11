import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import AgentRun, AgentRunStep, User
from app.services.agents.run_store import AgentRunStore


def test_agent_run_store_persists_completed_research_run(client, exchange):
    headers = exchange("researcher@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        user = db.get(User, me["id"])
        store = AgentRunStore(db)
        run = store.start(
            user_id=user.id,
            conversation_id=None,
            kind="research",
            input_data={"query": "Gemini Live API"},
        )
        store.step(run, "search", "running", detail={"query": "Gemini Live API"})
        store.step(
            run,
            "search",
            "completed",
            detail={"result_count": 1},
            evidence=(
                {
                    "title": "Gemini Live API",
                    "url": "https://ai.google.dev/api/live",
                    "excerpt_summary": "Live API documentation",
                }
                for _ in range(1)
            ),
        )
        store.complete(run, {"summary": "Gemini Live API supports realtime interaction."})
        db.commit()

        db.expire_all()
        saved_run = db.get(AgentRun, run.id)
        saved_steps = (
            db.query(AgentRunStep)
            .filter(AgentRunStep.run_id == run.id)
            .order_by(AgentRunStep.sequence)
            .all()
        )

    assert saved_run.status == "completed"
    assert json.loads(saved_run.input_json) == {"query": "Gemini Live API"}
    assert json.loads(saved_run.output_json) == {"summary": "Gemini Live API supports realtime interaction."}
    assert [(step.name, step.status) for step in saved_steps] == [
        ("search", "running"),
        ("search", "completed"),
    ]
    assert [step.sequence for step in saved_steps] == [1, 2]
    assert json.loads(saved_steps[1].evidence_json)[0]["url"] == "https://ai.google.dev/api/live"


def test_agent_run_store_rejects_another_users_conversation(client, exchange):
    owner_headers = exchange("owner@example.com")
    other_headers = exchange("other@example.com")
    conversation = client.post("/api/conversations", json={"title": "Private"}, headers=owner_headers).json()
    other_user = client.get("/api/auth/me", headers=other_headers).json()

    with client.app.state.SessionLocal() as db:
        store = AgentRunStore(db)
        with pytest.raises(ValueError, match="does not belong to user"):
            store.start(
                user_id=other_user["id"],
                conversation_id=conversation["id"],
                kind="research",
                input_data={"query": "private"},
            )
        assert db.query(AgentRun).filter(AgentRun.user_id == other_user["id"]).count() == 0


def test_sqlite_foreign_keys_reject_orphan_agent_runs(client):
    with client.app.state.SessionLocal() as db:
        assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1
        db.add(AgentRun(user_id="missing-user", kind="research"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_agent_run_store_allocates_sequences_across_sessions(client, exchange):
    headers = exchange("sequencer@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        run = AgentRunStore(db).start(
            user_id=me["id"], conversation_id=None, kind="research", input_data={"query": "sequence"}
        )
        run_id = run.id
        db.commit()

    with client.app.state.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        AgentRunStore(db).step(run, "search", "running")
        db.commit()

    with client.app.state.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        AgentRunStore(db).step(run, "search", "completed")
        db.commit()

    with client.app.state.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run_id).order_by(AgentRunStep.sequence).all()

    assert [step.sequence for step in steps] == [1, 2]
    assert run.next_step_sequence == 3


def test_agent_run_store_fail_persists_truncated_error(client, exchange):
    headers = exchange("failure@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = AgentRunStore(db)
        run = store.start(user_id=me["id"], conversation_id=None, kind="research", input_data={"query": "failure"})
        store.fail(run, "x" * 1001)
        db.commit()
        db.expire_all()
        saved_run = db.get(AgentRun, run.id)

    assert saved_run.status == "failed"
    assert saved_run.error == "x" * 1000
