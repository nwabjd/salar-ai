from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import threading

import pytest

from app.database import Base, create_session_factory
from app.models import Job, User, Workspace
from app.services.jobs.contracts import JobOutcome
from app.services.jobs.store import JobStore


@pytest.fixture
def session_factory(tmp_path):
    engine, factory = create_session_factory(f"sqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    with factory() as db:
        db.add_all(
            [
                User(id="user-a", email="a@example.com", password_hash="hash"),
                User(id="user-b", email="b@example.com", password_hash="hash"),
                Workspace(id="workspace-a", user_id="user-a", name="A"),
                Workspace(id="workspace-b", user_id="user-a", name="B"),
            ]
        )
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


def enqueue(store, *, owner_id="user-a", key="request-1", **kwargs):
    input_data = kwargs.pop("input_data", {"value": 1})
    return store.enqueue(
        owner_id=owner_id,
        kind="test.echo",
        input_data=input_data,
        idempotency_key=key,
        **kwargs,
    )


def test_enqueue_is_idempotent_per_owner_and_round_trips_json(session_factory):
    store = JobStore(session_factory)
    first = enqueue(store, input_data={"nested": {"items": [1, True, None]}})
    duplicate = enqueue(store, input_data={"value": 2})
    other_owner = enqueue(store, owner_id="user-b", input_data={"value": 3})

    assert duplicate.id == first.id
    assert duplicate.input_data == {"nested": {"items": [1, True, None]}}
    assert other_owner.id != first.id
    assert "lease_token" not in first.__dict__
    with pytest.raises(FrozenInstanceError):
        first.status = "running"


@pytest.mark.parametrize("input_data", [None, [], "text", 1])
def test_enqueue_requires_object_input(session_factory, input_data):
    with pytest.raises(ValueError, match="object"):
        JobStore(session_factory).enqueue(
            owner_id="user-a",
            kind="test.echo",
            input_data=input_data,
            idempotency_key="invalid",
        )


def test_claims_only_due_jobs_in_priority_schedule_creation_order(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    future = enqueue(store, key="future", priority=1, scheduled_at=now + timedelta(seconds=1))
    later_priority = enqueue(store, key="priority-20", priority=20, scheduled_at=now)
    first = enqueue(store, key="priority-10-a", priority=10, scheduled_at=now)
    second = enqueue(store, key="priority-10-b", priority=10, scheduled_at=now)
    with session_factory() as db:
        db.get(Job, first.id).created_at = now - timedelta(seconds=2)
        db.get(Job, second.id).created_at = now - timedelta(seconds=1)
        db.commit()

    claims = [store.claim_next(worker_id="worker", lease_seconds=30, now=now) for _ in range(3)]

    assert [claim.id for claim in claims] == [first.id, second.id, later_priority.id]
    assert store.claim_next(worker_id="worker", lease_seconds=30, now=now) is None
    assert store.get_for_owner(owner_id="user-a", job_id=future.id).status == "queued"


def test_lists_by_workspace_status_and_cursor(session_factory):
    store = JobStore(session_factory)
    in_a = enqueue(store, key="workspace-a", workspace_id="workspace-a")
    enqueue(store, key="workspace-b", workspace_id="workspace-b")
    unscoped = enqueue(store, key="unscoped")

    assert [job.id for job in store.list_for_owner(owner_id="user-a", workspace_id="workspace-a")] == [in_a.id]
    assert {job.id for job in store.list_for_owner(owner_id="user-a", statuses={"queued"})} == {
        in_a.id,
        unscoped.id,
        store.list_for_owner(owner_id="user-a", workspace_id="workspace-b")[0].id,
    }
    newest = store.list_for_owner(owner_id="user-a", limit=1)[0]
    older = store.list_for_owner(owner_id="user-a", before=newest.created_at)
    assert newest.id not in {job.id for job in older}


def test_transitions_append_ordered_events_and_progress_is_monotonic(session_factory):
    store = JobStore(session_factory)
    job = enqueue(store)
    claim = store.claim_next(worker_id="worker", lease_seconds=30)

    assert claim.id == job.id
    assert store.record_progress(
        job_id=job.id,
        lease_token=claim.lease_token,
        progress=0.75,
        event_type="job.progress",
        payload={"message": "Almost done"},
    )
    assert store.record_progress(
        job_id=job.id,
        lease_token=claim.lease_token,
        progress=0.25,
        event_type="job.progress",
        payload={"message": "Late stale update"},
    )
    assert store.complete(
        job_id=job.id,
        lease_token=claim.lease_token,
        outcome=JobOutcome(status="completed", result={"echo": {"ok": True}}),
    )

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    events = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "completed"
    assert snapshot.progress == 1.0
    assert snapshot.result == {"echo": {"ok": True}}
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert [event["event_type"] for event in events] == [
        "job.queued",
        "job.claimed",
        "job.progress",
        "job.progress",
        "job.completed",
    ]
    assert events[2]["payload"] == {"message": "Almost done"}


def test_invalid_terminal_transition_and_stale_progress_are_rejected(session_factory):
    store = JobStore(session_factory)
    job = enqueue(store)
    claim = store.claim_next(worker_id="worker", lease_seconds=30)
    outcome = JobOutcome(status="completed", result={})

    assert store.complete(job_id=job.id, lease_token="wrong", outcome=outcome) is False
    assert store.record_progress(
        job_id=job.id, lease_token="wrong", progress=0.5, event_type="job.progress", payload={}
    ) is False
    assert store.complete(job_id=job.id, lease_token=claim.lease_token, outcome=outcome) is True
    assert store.complete(job_id=job.id, lease_token=claim.lease_token, outcome=outcome) is False


def test_two_workers_cannot_claim_same_sqlite_job(session_factory):
    store = JobStore(session_factory)
    job = enqueue(store)
    ready = threading.Barrier(2, timeout=10)

    def claim(worker_id):
        ready.wait()
        return JobStore(session_factory).claim_next(worker_id=worker_id, lease_seconds=30)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(claim, ("worker-a", "worker-b")))

    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0].id == job.id


def test_expired_lease_is_recovered_and_old_token_is_fenced(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, scheduled_at=now)
    old_claim = store.claim_next(worker_id="worker-old", lease_seconds=10, now=now)

    assert store.recover_abandoned(now=now + timedelta(seconds=11)) == 1
    recovered = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert recovered.status == "retrying"
    new_claim = store.claim_next(worker_id="worker-new", lease_seconds=10, now=now + timedelta(seconds=11))
    assert new_claim.id == job.id
    assert new_claim.lease_token != old_claim.lease_token
    assert store.heartbeat(
        job_id=job.id, lease_token=old_claim.lease_token, lease_seconds=10, now=now + timedelta(seconds=12)
    ) is False
    assert store.complete(
        job_id=job.id,
        lease_token=old_claim.lease_token,
        outcome=JobOutcome(status="completed", result={"stale": True}),
        now=now + timedelta(seconds=12),
    ) is False


@pytest.mark.parametrize("operation", ["progress", "complete", "fail"])
def test_expired_lease_cannot_mutate_before_recovery(session_factory, operation):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=1, now=now)
    expired_at = now + timedelta(seconds=2)

    if operation == "progress":
        result = store.record_progress(
            job_id=job.id,
            lease_token=claim.lease_token,
            progress=0.8,
            event_type="job.progress",
            payload={"message": "late"},
            now=expired_at,
        )
        assert result is False
    elif operation == "complete":
        result = store.complete(
            job_id=job.id,
            lease_token=claim.lease_token,
            outcome=JobOutcome(status="completed", result={"late": True}),
            now=expired_at,
        )
        assert result is False
    else:
        result = store.fail_or_retry(
            job_id=job.id,
            lease_token=claim.lease_token,
            code="temporary",
            safe_detail="Retrying.",
            now=expired_at,
        )
        assert result == "stale"

    unchanged = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert unchanged.status == "running"
    assert unchanged.progress == 0.0
    assert unchanged.result is None
    assert unchanged.safe_error_code is None
    assert unchanged.safe_error_detail is None
    assert [event["event_type"] for event in store.list_events_for_owner(owner_id="user-a", job_id=job.id)] == [
        "job.queued",
        "job.claimed",
    ]


def test_retry_exhaustion_is_terminal_and_sanitized(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    status = store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="provider_unavailable",
        safe_detail="Please try again later.",
        now=now,
    )

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert status == "failed"
    assert snapshot.status == "failed"
    assert snapshot.safe_error_code == "provider_unavailable"
    assert snapshot.safe_error_detail == "Please try again later."
    assert snapshot.attempt_count == 1
    assert "lease_token" not in snapshot.__dict__
    with session_factory() as db:
        persisted = db.get(Job, job.id)
        assert "Traceback" not in (persisted.safe_error_detail or "")


def test_fail_or_retry_replaces_exception_diagnostics_with_generic_safe_error(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)
    diagnostic = RuntimeError(
        "Traceback: SELECT password FROM users; File C:\\srv\\jobs.py; "
        "api_key=sk-secret token=private password=hunter2 Authorization: Bearer abc.def"
    )

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="SQL/DROP_TABLE/password=secret",
        safe_detail=diagnostic,
        now=now,
    ) == "failed"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    events = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    persisted_text = f"{snapshot.safe_error_code} {snapshot.safe_error_detail} {events[-1]['payload']}".lower()
    assert snapshot.safe_error_code == "job_execution_failed"
    assert snapshot.safe_error_detail == "The job could not be completed."
    assert len(snapshot.safe_error_code) <= 80
    assert len(snapshot.safe_error_detail) <= 500
    for secret in ("traceback", "select", "c:\\srv", "api_key", "sk-secret", "private", "hunter2", "bearer"):
        assert secret not in persisted_text


@pytest.mark.parametrize(
    ("credential", "sensitive_prefix"),
    [
        ("sk-proj-abcdefghijklmnopqrstuvwxyz1234567890", "sk-proj-"),
        ("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890", "ghp_"),
        (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwic2VjcmV0IjoidGVzdCJ9."
            "c2lnbmF0dXJlMTIzNDU2Nzg5MA",
            "eyj",
        ),
    ],
)
def test_fail_or_retry_redacts_unlabelled_credential_strings(
    session_factory, credential, sensitive_prefix
):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="credential_rejected",
        safe_detail=f"Provider rejected credential {credential}",
        now=now,
    ) == "failed"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    event = store.list_events_for_owner(owner_id="user-a", job_id=job.id)[-1]
    persisted_text = f"{snapshot.safe_error_detail} {event['payload']}".lower()
    assert snapshot.safe_error_code == "job_execution_failed"
    assert snapshot.safe_error_detail == "The job could not be completed."
    assert credential.lower() not in persisted_text
    assert sensitive_prefix.lower() not in persisted_text


@pytest.mark.parametrize(
    "credential_code",
    [
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890",
        "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
        (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "c2lnbmF0dXJlMTIzNDU2Nzg5MA"
        ),
    ],
)
def test_fail_or_retry_redacts_credentials_from_error_code(session_factory, credential_code):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code=credential_code,
        safe_detail="Please try again later.",
        now=now,
    ) == "failed"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    event = store.list_events_for_owner(owner_id="user-a", job_id=job.id)[-1]
    persisted_text = f"{snapshot.safe_error_code} {event['payload']}".lower()
    assert snapshot.safe_error_code == "job_execution_failed"
    assert snapshot.safe_error_detail == "Please try again later."
    assert credential_code.lower() not in persisted_text


@pytest.mark.parametrize(
    "unsafe_detail",
    [
        "postgresql://alice:s3cr3t@example.test/private_db",
        "-----BEGIN PRIVATE KEY----- MIIEvQIBADANBgkqhkiG9w0 -----END PRIVATE KEY-----",
        "AWS access failed for AKIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "Cloud API rejected AIzaSyDUMMYDUMMYDUMMYDUMMYDUMMYDUMMYDUM",
    ],
)
def test_fail_or_retry_redacts_uri_private_key_and_cloud_credentials(session_factory, unsafe_detail):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="provider_unavailable",
        safe_detail=unsafe_detail,
        now=now,
    ) == "failed"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    event = store.list_events_for_owner(owner_id="user-a", job_id=job.id)[-1]
    persisted_text = f"{snapshot.safe_error_code} {snapshot.safe_error_detail} {event['payload']}".lower()
    assert snapshot.safe_error_code == "job_execution_failed"
    assert snapshot.safe_error_detail == "The job could not be completed."
    assert unsafe_detail.lower() not in persisted_text


def test_fail_or_retry_normalizes_safe_code_without_changing_safe_detail(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="PROVIDER_UNAVAILABLE",
        safe_detail="Please try again later.",
        now=now,
    ) == "failed"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.safe_error_code == "provider_unavailable"
    assert snapshot.safe_error_detail == "Please try again later."


def test_retry_uses_deterministic_backoff_and_can_be_claimed_when_due(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=2, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert store.fail_or_retry(
        job_id=job.id,
        lease_token=claim.lease_token,
        code="temporary",
        safe_detail="Retrying.",
        now=now,
    ) == "retrying"
    retrying = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert retrying.scheduled_at > now
    assert store.claim_next(worker_id="worker", lease_seconds=30, now=now) is None
    assert store.claim_next(worker_id="worker", lease_seconds=30, now=retrying.scheduled_at).id == job.id


def test_queued_and_running_cancellation(session_factory):
    store = JobStore(session_factory)
    queued = enqueue(store, key="queued")
    cancelled = store.request_cancel(owner_id="user-a", job_id=queued.id)
    assert cancelled.status == "cancelled"
    assert cancelled.finished_at is not None
    assert store.claim_next(worker_id="worker", lease_seconds=30) is None

    running = enqueue(store, key="running")
    claim = store.claim_next(worker_id="worker", lease_seconds=30)
    requested = store.request_cancel(owner_id="user-a", job_id=running.id)
    assert requested.status == "running"
    assert requested.cancel_requested_at is not None
    assert store.is_cancel_requested(job_id=running.id, lease_token=claim.lease_token) is True
    assert store.is_cancel_requested(job_id=running.id, lease_token="wrong") is False
    assert store.heartbeat(job_id=running.id, lease_token=claim.lease_token, lease_seconds=30) is True


@pytest.mark.parametrize("terminal_operation", ["complete", "fail"])
def test_cancel_request_fences_late_worker_terminal_writes(session_factory, terminal_operation):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)
    requested = store.request_cancel(owner_id="user-a", job_id=job.id, now=now + timedelta(seconds=1))
    assert requested.status == "running"

    if terminal_operation == "complete":
        result = store.complete(
            job_id=job.id,
            lease_token=claim.lease_token,
            outcome=JobOutcome(status="completed", result={"late": True}),
            now=now + timedelta(seconds=2),
        )
        assert result is False
    else:
        result = store.fail_or_retry(
            job_id=job.id,
            lease_token=claim.lease_token,
            code="temporary",
            safe_detail="Retrying.",
            now=now + timedelta(seconds=2),
        )
        assert result == "cancelled"

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    events = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "cancelled"
    assert snapshot.result is None
    assert [event["event_type"] for event in events] == [
        "job.queued",
        "job.claimed",
        "job.cancel_requested",
        "job.cancelled",
    ]


@pytest.mark.parametrize("terminal_operation", ["complete", "fail"])
def test_cancel_request_fences_late_worker_across_sessions(session_factory, terminal_operation):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, scheduled_at=now)
    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)
    cancel_committed = threading.Event()

    def cancel():
        result = JobStore(session_factory).request_cancel(
            owner_id="user-a", job_id=job.id, now=now + timedelta(seconds=1)
        )
        cancel_committed.set()
        return result

    def finalize_late():
        assert cancel_committed.wait(timeout=10)
        late_store = JobStore(session_factory)
        if terminal_operation == "complete":
            return late_store.complete(
                job_id=job.id,
                lease_token=claim.lease_token,
                outcome=JobOutcome(status="completed", result={"late": True}),
                now=now + timedelta(seconds=2),
            )
        return late_store.fail_or_retry(
            job_id=job.id,
            lease_token=claim.lease_token,
            code="temporary",
            safe_detail="Retrying.",
            now=now + timedelta(seconds=2),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        cancel_future = executor.submit(cancel)
        finalize_future = executor.submit(finalize_late)
        assert cancel_future.result(timeout=10).status == "running"
        expected = False if terminal_operation == "complete" else "cancelled"
        assert finalize_future.result(timeout=10) == expected

    assert store.get_for_owner(owner_id="user-a", job_id=job.id).status == "cancelled"


def test_expired_cancel_request_is_recovered_as_cancelled_and_not_reclaimed(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, scheduled_at=now)
    store.claim_next(worker_id="worker", lease_seconds=1, now=now)
    store.request_cancel(owner_id="user-a", job_id=job.id, now=now + timedelta(milliseconds=500))
    recovery_done = threading.Event()

    def recover():
        result = JobStore(session_factory).recover_abandoned(now=now + timedelta(seconds=2))
        recovery_done.set()
        return result

    def claim_after_recovery():
        assert recovery_done.wait(timeout=10)
        return JobStore(session_factory).claim_next(
            worker_id="replacement", lease_seconds=30, now=now + timedelta(seconds=2)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        recover_future = executor.submit(recover)
        claim_future = executor.submit(claim_after_recovery)
        assert recover_future.result(timeout=10) == 1
        assert claim_future.result(timeout=10) is None

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    events = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "cancelled"
    assert snapshot.finished_at == now + timedelta(seconds=2)
    assert [event["event_type"] for event in events] == [
        "job.queued",
        "job.claimed",
        "job.cancel_requested",
        "job.cancelled",
    ]


def test_claim_skips_claimable_rows_with_cancellation_requests(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    cancelled = enqueue(store, key="cancelled", priority=1, scheduled_at=now)
    valid = enqueue(store, key="valid", priority=2, scheduled_at=now)
    with session_factory() as db:
        db.get(Job, cancelled.id).cancel_requested_at = now
        db.commit()

    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert claim.id == valid.id
    assert store.get_for_owner(owner_id="user-a", job_id=cancelled.id).status == "queued"


def test_owner_isolation_for_reads_lists_cancellation_and_events(session_factory):
    store = JobStore(session_factory)
    job = enqueue(store)
    assert store.get_for_owner(owner_id="user-b", job_id=job.id) is None
    assert store.list_for_owner(owner_id="user-b") == []
    assert store.list_events_for_owner(owner_id="user-b", job_id=job.id) == []
    assert store.request_cancel(owner_id="user-b", job_id=job.id) is None
    assert store.get_for_owner(owner_id="user-a", job_id=job.id).status == "queued"


def test_recover_abandoned_fails_exhausted_jobs(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    job = enqueue(store, max_attempts=1, scheduled_at=now)
    store.claim_next(worker_id="worker", lease_seconds=1, now=now)

    assert store.recover_abandoned(now=now + timedelta(seconds=2)) == 1
    recovered = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert recovered.status == "failed"
    assert recovered.safe_error_code == "job_lease_expired"
    assert recovered.finished_at == now + timedelta(seconds=2)


def test_malformed_input_is_failed_without_consuming_attempt_and_valid_job_is_claimed(session_factory):
    store = JobStore(session_factory)
    now = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
    malformed = enqueue(store, key="malformed", priority=1, scheduled_at=now)
    valid = enqueue(store, key="valid", priority=2, scheduled_at=now)
    raw_secret = '{"credential": "sk-proj-raw-secret-without-closing-brace"'
    with session_factory() as db:
        row = db.get(Job, malformed.id)
        row.input_json = raw_secret
        row.result_json = "[malformed-result"
        db.commit()

    claim = store.claim_next(worker_id="worker", lease_seconds=30, now=now)

    assert claim.id == valid.id
    malformed_snapshot = store.get_for_owner(owner_id="user-a", job_id=malformed.id)
    listed = {job.id: job for job in store.list_for_owner(owner_id="user-a")}
    events = store.list_events_for_owner(owner_id="user-a", job_id=malformed.id)
    assert malformed_snapshot.status == "failed"
    assert malformed_snapshot.input_data == {}
    assert malformed_snapshot.result == {}
    assert listed[malformed.id].input_data == {}
    assert malformed_snapshot.attempt_count == 0
    assert malformed_snapshot.safe_error_code == "invalid_job_input"
    assert "lease_token" not in malformed_snapshot.__dict__
    assert [event["event_type"] for event in events] == ["job.queued", "job.failed"]
    assert raw_secret not in str(events)
    with session_factory() as db:
        malformed_row = db.get(Job, malformed.id)
        assert malformed_row.lease_token is None
        assert malformed_row.lease_expires_at is None
