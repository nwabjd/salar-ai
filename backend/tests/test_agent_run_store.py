import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app.database import Base, create_session_factory
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


def test_agent_run_store_allocates_without_update_returning(tmp_path, monkeypatch):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'no-returning.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="no-returning@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            run = AgentRunStore(db).start(
                user_id=user.id, conversation_id=None, kind="research", input_data={"query": "compatibility"}
            )
            run_id = run.id
            db.commit()

        monkeypatch.setattr(engine.dialect, "update_returning", False)
        @event.listens_for(engine, "before_cursor_execute")
        def reject_returning(connection, cursor, statement, parameters, context, executemany):
            if " RETURNING " in statement.upper():
                raise AssertionError("SQLite compatibility path must not use RETURNING")

        with session_factory() as db:
            run = db.get(AgentRun, run_id)
            AgentRunStore(db).step(run, "search", "running")
            db.commit()
    finally:
        engine.dispose()


def test_agent_run_store_allocates_unique_sequences_for_overlapping_sqlite_sessions(tmp_path):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'concurrent-runs.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="concurrent@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            run = AgentRunStore(db).start(
                user_id=user.id, conversation_id=None, kind="research", input_data={"query": "concurrent"}
            )
            run_id = run.id
            db.commit()

        ready = threading.Barrier(2, timeout=10)

        def add_step(status):
            with session_factory() as db:
                run = db.get(AgentRun, run_id)
                ready.wait()
                AgentRunStore(db).step(run, "search", status)
                db.commit()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(add_step, status) for status in ("running", "completed")]
            for future in futures:
                future.result(timeout=10)

        with session_factory() as db:
            run = db.get(AgentRun, run_id)
            sequences = [
                step.sequence
                for step in db.query(AgentRunStep)
                .filter(AgentRunStep.run_id == run_id)
                .order_by(AgentRunStep.sequence)
            ]

        assert sequences == [1, 2]
        assert run.next_step_sequence == 3
    finally:
        engine.dispose()
