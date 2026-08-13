import json
import time
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Job, JobEvent, User
from app.services.jobs.store import JobStore, utcnow


def test_job_store_enqueue_claim_complete(client, exchange):
    headers = exchange("jobber@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        job = store.enqueue(user_id=me["id"], kind="test.ping", input_data={"n": 1}, priority=1)
        job_id = job.id
        db.commit()
        assert job.status == "queued"

        claimed = store.claim(worker_id="w1", limit=5)
        assert len(claimed) == 1
        claimed_job, token = claimed[0]
        assert claimed_job.id == job_id
        assert claimed_job.status == "running"
        assert claimed_job.attempts == 1

        assert store.complete(claimed_job, token, output={"pong": True})
        db.commit()

    with client.app.state.SessionLocal() as db:
        saved = db.get(Job, job_id)
        assert saved.status == "completed"
        assert json.loads(saved.output_json) == {"pong": True}
        events = db.query(JobEvent).filter(JobEvent.job_id == job_id).order_by(JobEvent.sequence).all()
        assert [(e.name, e.status) for e in events] == [
            ("enqueue", "queued"),
            ("claim", "running"),
            ("complete", "completed"),
        ]
        assert [e.sequence for e in events] == [1, 2, 3]


def test_job_store_claim_is_fenced_against_second_worker(client, exchange):
    headers = exchange("fence@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        job = store.enqueue(user_id=me["id"], kind="test.fenced")
        db.commit()

        first = store.claim(worker_id="w1", limit=5)
        assert len(first) == 1
        fenced_job, first_token = first[0]
        db.commit()

        # A second worker cannot see the running job.
        second = store.claim(worker_id="w2", limit=5)
        assert second == []

        # The wrong token cannot complete or fail the job.
        assert not store.complete(fenced_job, "wrong-token", output={})
        assert not store.fail(fenced_job, "wrong-token", "nope")
        # The correct token can.
        assert store.complete(fenced_job, first_token, output={"ok": True})
        db.commit()


def test_job_store_fail_retries_with_backoff_then_terminates(client, exchange):
    headers = exchange("retry@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        job = store.enqueue(user_id=me["id"], kind="test.retry", max_attempts=2)
        db.commit()

        claim1, token1 = store.claim(worker_id="w1", limit=5)[0]
        assert store.fail(claim1, token1, "boom", retry=True)
        db.commit()
        assert claim1.status == "queued"
        assert claim1.next_attempt_at is not None

        # Fast-forward the retry so the next claim can see it immediately.
        claim1.next_attempt_at = utcnow() - timedelta(seconds=1)
        db.commit()

        claim2, token2 = store.claim(worker_id="w1", limit=5)[0]
        assert claim2.id == claim1.id
        assert claim2.attempts == 2
        assert store.fail(claim2, token2, "boom again", retry=True)
        db.commit()
        assert claim2.status == "failed"
        assert claim2.finished_at is not None


def test_job_store_unknown_kind_is_not_claimed_twice(client, exchange):
    headers = exchange("unknown@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        job = store.enqueue(user_id=me["id"], kind="test.unknown")
        db.commit()
        claimed, token = store.claim(worker_id="w1", limit=5)[0]
        assert store.complete(claimed, token, output={"ok": True})
        db.commit()


def test_job_store_cancel_respects_ownership(client, exchange):
    owner = exchange("cancel-owner@example.com")
    other = exchange("cancel-other@example.com")
    owner_me = client.get("/api/auth/me", headers=owner).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        job = store.enqueue(user_id=owner_me["id"], kind="test.cancel")
        db.commit()

        assert not store.cancel(job.id, "someone-else")
        assert store.cancel(job.id, owner_me["id"])
        db.commit()
        assert db.get(Job, job.id).status == "cancelled"
        # Cancelling a terminal job is a no-op.
        assert not store.cancel(job.id, owner_me["id"])


def test_job_store_has_pending_deduplicates(client, exchange):
    headers = exchange("pending@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = JobStore(db)
        assert not store.has_pending(me["id"], "intel.email_watch")
        store.enqueue(user_id=me["id"], kind="intel.email_watch")
        db.commit()
        assert store.has_pending(me["id"], "intel.email_watch")

        claimed, token = store.claim(worker_id="w1", limit=5)[0]
        db.commit()
        assert store.has_pending(me["id"], "intel.email_watch")

        store.complete(claimed, token, output={})
        db.commit()
        assert not store.has_pending(me["id"], "intel.email_watch")


def test_job_store_sqlite_foreign_keys_reject_orphan_jobs(client):
    with client.app.state.SessionLocal() as db:
        db.add(Job(user_id="missing-user", kind="test"))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


def test_job_store_lists_for_user_sorted_newest_first(client, exchange):
    headers = exchange("list@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        JobStore(db).enqueue(user_id=me["id"], kind="test.a")
        db.commit()
    time.sleep(0.05)  # ensure a distinct created_at timestamp
    with client.app.state.SessionLocal() as db:
        JobStore(db).enqueue(user_id=me["id"], kind="test.b")
        db.commit()

    with client.app.state.SessionLocal() as db:
        jobs = JobStore(db).list_for_user(me["id"])
        assert [j.kind for j in jobs] == ["test.b", "test.a"]
