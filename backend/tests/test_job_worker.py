import asyncio
from datetime import datetime, timedelta, timezone
import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.database import Base, create_session_factory
from app.models import Job, User
from app.services.jobs.contracts import (
    JobCancelled,
    JobOutcome,
    PermanentJobError,
    RetryableJobError,
)
from app.services.jobs.registry import JobRegistry
from app.services.jobs.store import JobStore, retry_delay_seconds
from app.services.jobs.worker import JobExecutionContext, JobLeaseLost, JobWorker


NOW = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self, value=NOW):
        self.value = value

    def __call__(self):
        return self.value


@pytest.fixture
def worker_session_factory(tmp_path):
    engine, factory = create_session_factory(f"sqlite:///{tmp_path / 'worker.db'}")
    Base.metadata.create_all(engine)
    with factory() as db:
        db.add(User(id="user-a", email="a@example.com", password_hash="hash"))
        db.commit()
    try:
        yield factory
    finally:
        engine.dispose()


def enqueue(store, *, kind="test.echo", key="job-1", max_attempts=3, scheduled_at=NOW):
    return store.enqueue(
        owner_id="user-a",
        kind=kind,
        input_data={"value": 7},
        idempotency_key=key,
        max_attempts=max_attempts,
        scheduled_at=scheduled_at,
    )


def make_worker(factory, registry, clock=None, **kwargs):
    return JobWorker(
        store=JobStore(factory),
        registry=registry,
        worker_id=kwargs.pop("worker_id", "worker-a"),
        lease_seconds=kwargs.pop("lease_seconds", 30),
        clock=clock or MutableClock(),
        **kwargs,
    )


def test_registry_rejects_invalid_and_duplicate_kinds_without_exposing_mutable_state():
    registry = JobRegistry()

    async def handler(context, payload):
        return JobOutcome(status="completed", result=payload)

    registry.register("test.echo", handler)

    assert registry.resolve("test.echo") is handler
    assert registry.resolve("missing") is None
    assert registry.registered_kinds == ("test.echo",)
    with pytest.raises(ValueError, match="non-empty"):
        registry.register("", handler)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("test.echo", handler)
    with pytest.raises(TypeError, match="async"):
        registry.register("test.sync", lambda context, payload: None)
    with pytest.raises(AttributeError):
        registry.registered_kinds.append("mutated")


@pytest.mark.asyncio
async def test_worker_completes_job_records_progress_result_and_events(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store)
    registry = JobRegistry()

    async def handler(context, payload):
        assert context.job_id == job.id
        assert context.owner_id == "user-a"
        assert context.workspace_id is None
        assert not hasattr(context, "lease_token")
        await context.progress(0.4, {"message": "working"})
        return JobOutcome(status="completed", result={"echo": payload})

    registry.register("test.echo", handler)

    assert await make_worker(worker_session_factory, registry).run_once() is True

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    events = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "completed"
    assert snapshot.result == {"echo": {"value": 7}}
    assert snapshot.progress == 1.0
    assert [event["event_type"] for event in events] == [
        "job.queued",
        "job.claimed",
        "job.progress",
        "job.completed",
    ]
    assert events[2]["payload"] == {"message": "working"}


@pytest.mark.asyncio
async def test_context_approval_is_explicitly_unsupported_until_task_three(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store)
    registry = JobRegistry()

    async def handler(context, payload):
        with pytest.raises(NotImplementedError, match="Task 3"):
            await context.request_approval("email.send", {"to": "safe@example.com"})
        return JobOutcome(status="completed", result={})

    registry.register("test.echo", handler)
    assert await make_worker(worker_session_factory, registry).run_once() is True
    assert store.get_for_owner(owner_id="user-a", job_id=job.id).status == "completed"


@pytest.mark.asyncio
async def test_unknown_kind_is_terminally_failed(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, kind="missing.kind")

    assert await make_worker(worker_session_factory, JobRegistry()).run_once() is True

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "failed"
    assert snapshot.attempt_count == 1
    assert snapshot.safe_error_code == "unknown_job_kind"
    assert snapshot.safe_error_detail == "This job type is unavailable."


@pytest.mark.asyncio
async def test_retryable_failure_uses_configured_deterministic_backoff_then_succeeds(worker_session_factory):
    store = JobStore(worker_session_factory)
    clock = MutableClock()
    job = enqueue(store, max_attempts=2)
    registry = JobRegistry()
    attempts = 0

    async def handler(context, payload):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RetryableJobError("provider_unavailable", "caller detail ignored")
        return JobOutcome(status="completed", result={"attempts": attempts})

    registry.register("test.echo", handler)
    worker = make_worker(
        worker_session_factory,
        registry,
        clock=clock,
        retry_base_seconds=7,
        retry_max_seconds=20,
    )

    assert await worker.run_once() is True
    retrying = store.get_for_owner(owner_id="user-a", job_id=job.id)
    expected_delay = retry_delay_seconds(job.id, 1, retry_base_seconds=7, retry_max_seconds=20)
    assert retrying.status == "retrying"
    assert retrying.scheduled_at == NOW + timedelta(seconds=expected_delay)

    clock.value = retrying.scheduled_at
    assert await worker.run_once() is True
    completed = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert completed.status == "completed"
    assert completed.result == {"attempts": 2}


@pytest.mark.asyncio
async def test_permanent_failure_does_not_retry(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, max_attempts=5)
    registry = JobRegistry()

    async def handler(context, payload):
        raise PermanentJobError("invalid_job_payload", "unsafe caller detail")

    registry.register("test.echo", handler)
    assert await make_worker(worker_session_factory, registry).run_once() is True

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "failed"
    assert snapshot.attempt_count == 1
    assert snapshot.safe_error_code == "invalid_job_payload"
    assert snapshot.safe_error_detail == "The job payload is invalid."


@pytest.mark.asyncio
async def test_unexpected_exception_is_logged_but_persisted_as_vetted_generic_error(
    worker_session_factory, caplog
):
    store = JobStore(worker_session_factory)
    job = enqueue(store, max_attempts=1)
    registry = JobRegistry()
    secret = "sk-proj-do-not-persist"

    async def handler(context, payload):
        raise RuntimeError(f"database password and {secret}")

    registry.register("test.echo", handler)
    with caplog.at_level("ERROR"):
        assert await make_worker(worker_session_factory, registry).run_once() is True

    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    event_text = str(store.list_events_for_owner(owner_id="user-a", job_id=job.id)[-1])
    assert snapshot.status == "failed"
    assert snapshot.safe_error_code == "job_execution_failed"
    assert snapshot.safe_error_detail == "The job could not be completed."
    assert secret not in event_text
    assert secret in caplog.text


@pytest.mark.asyncio
async def test_handler_cooperatively_acknowledges_cancellation(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store)
    registry = JobRegistry()
    started = asyncio.Event()
    check_cancel = asyncio.Event()

    async def handler(context, payload):
        started.set()
        await check_cancel.wait()
        await context.raise_if_cancelled()
        raise AssertionError("cancellation check did not raise")

    registry.register("test.echo", handler)
    task = asyncio.create_task(make_worker(worker_session_factory, registry).run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    store.request_cancel(owner_id="user-a", job_id=job.id)
    check_cancel.set()

    assert await asyncio.wait_for(task, timeout=1) is True
    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "cancelled"
    assert [event["event_type"] for event in store.list_events_for_owner(owner_id="user-a", job_id=job.id)][-2:] == [
        "job.cancel_requested",
        "job.cancelled",
    ]


@pytest.mark.asyncio
async def test_heartbeat_prevents_theft_after_original_lease_expiry(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, scheduled_at=None)
    registry = JobRegistry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(context, payload):
        started.set()
        await release.wait()
        return JobOutcome(status="completed", result={})

    registry.register("test.echo", handler)
    worker = JobWorker(
        store=store,
        registry=registry,
        worker_id="long-worker",
        lease_seconds=0.3,
        heartbeat_interval=0.05,
    )
    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.36)

    assert JobStore(worker_session_factory).recover_abandoned() == 0
    assert JobStore(worker_session_factory).claim_next(worker_id="thief", lease_seconds=1) is None
    release.set()
    assert await asyncio.wait_for(task, timeout=1) is True
    assert store.get_for_owner(owner_id="user-a", job_id=job.id).status == "completed"


@pytest.mark.asyncio
async def test_lost_heartbeat_ownership_cancels_handler_without_terminal_write(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, scheduled_at=None)
    registry = JobRegistry()
    started = asyncio.Event()
    handler_cancelled = asyncio.Event()

    async def handler(context, payload):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            handler_cancelled.set()

    registry.register("test.echo", handler)
    worker = JobWorker(
        store=store,
        registry=registry,
        worker_id="loser",
        lease_seconds=1,
        heartbeat_interval=0.02,
    )
    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    with worker_session_factory() as db:
        row = db.get(Job, job.id)
        row.lease_token = "replacement-token"
        db.commit()

    await asyncio.wait_for(handler_cancelled.wait(), timeout=1)
    assert await asyncio.wait_for(task, timeout=1) is True
    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "running"
    assert snapshot.result is None
    assert snapshot.safe_error_code is None
    assert [event["event_type"] for event in store.list_events_for_owner(owner_id="user-a", job_id=job.id)] == [
        "job.queued",
        "job.claimed",
    ]


@pytest.mark.asyncio
async def test_heartbeat_exception_cancels_handler_without_terminal_write(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, scheduled_at=None)
    registry = JobRegistry()
    started = asyncio.Event()
    handler_cancelled = asyncio.Event()

    async def handler(context, payload):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            handler_cancelled.set()

    def broken_heartbeat(**kwargs):
        raise RuntimeError("heartbeat database unavailable")

    registry.register("test.echo", handler)
    store.heartbeat = broken_heartbeat
    worker = JobWorker(
        store=store,
        registry=registry,
        worker_id="uncertain-owner",
        lease_seconds=1,
        heartbeat_interval=0.02,
    )

    assert await asyncio.wait_for(worker.run_once(), timeout=1) is True
    assert handler_cancelled.is_set()
    snapshot = JobStore(worker_session_factory).get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "running"
    assert snapshot.result is None
    assert snapshot.safe_error_code is None
    assert [
        event["event_type"]
        for event in JobStore(worker_session_factory).list_events_for_owner(owner_id="user-a", job_id=job.id)
    ] == ["job.queued", "job.claimed"]


@pytest.mark.asyncio
async def test_fence_external_action_renews_immediately_and_rejects_stale_context(worker_session_factory):
    store = JobStore(worker_session_factory)
    clock = MutableClock()
    job = enqueue(store)
    claim = store.claim_next(worker_id="old", lease_seconds=10, now=clock())
    context = JobExecutionContext(store=store, claim=claim, lease_seconds=10, clock=clock)

    clock.value = NOW + timedelta(seconds=9)
    await context.fence_external_action()
    with worker_session_factory() as db:
        renewed_expiry = db.get(Job, job.id).lease_expires_at.replace(tzinfo=timezone.utc)
    assert renewed_expiry == NOW + timedelta(seconds=19)

    clock.value = NOW + timedelta(seconds=20)
    store.recover_abandoned(now=clock())
    replacement = store.claim_next(worker_id="new", lease_seconds=10, now=clock())
    assert replacement.id == job.id
    with pytest.raises(JobLeaseLost):
        await context.fence_external_action()


@pytest.mark.asyncio
async def test_fence_external_action_rejects_an_already_requested_cancellation(worker_session_factory):
    store = JobStore(worker_session_factory)
    clock = MutableClock()
    job = enqueue(store)
    claim = store.claim_next(worker_id="worker", lease_seconds=10, now=clock())
    context = JobExecutionContext(store=store, claim=claim, lease_seconds=10, clock=clock)
    store.request_cancel(owner_id="user-a", job_id=job.id, now=NOW + timedelta(seconds=1))
    clock.value = NOW + timedelta(seconds=2)

    with pytest.raises(JobCancelled):
        await context.fence_external_action()

    with worker_session_factory() as db:
        row = db.get(Job, job.id)
        assert row.lease_expires_at.replace(tzinfo=timezone.utc) == NOW + timedelta(seconds=10)


@pytest.mark.asyncio
async def test_restart_recovery_allows_new_worker_and_fences_old_context(worker_session_factory):
    store = JobStore(worker_session_factory)
    clock = MutableClock()
    job = enqueue(store, max_attempts=2)
    old_claim = store.claim_next(worker_id="old", lease_seconds=1, now=clock())
    old_context = JobExecutionContext(store=store, claim=old_claim, lease_seconds=1, clock=clock)
    registry = JobRegistry()

    async def handler(context, payload):
        return JobOutcome(status="completed", result={"worker": "new"})

    registry.register("test.echo", handler)
    clock.value = NOW + timedelta(seconds=2)
    assert await make_worker(worker_session_factory, registry, clock=clock, worker_id="new").run_once() is True
    assert store.get_for_owner(owner_id="user-a", job_id=job.id).result == {"worker": "new"}
    with pytest.raises(JobLeaseLost):
        await old_context.progress(1.0, {"late": True})


@pytest.mark.asyncio
async def test_retry_exhaustion_becomes_failed(worker_session_factory):
    store = JobStore(worker_session_factory)
    clock = MutableClock()
    job = enqueue(store, max_attempts=2)
    registry = JobRegistry()

    async def handler(context, payload):
        raise RetryableJobError("provider_unavailable", "ignored")

    registry.register("test.echo", handler)
    worker = make_worker(worker_session_factory, registry, clock=clock, retry_base_seconds=1, retry_max_seconds=1)
    assert await worker.run_once() is True
    clock.value = store.get_for_owner(owner_id="user-a", job_id=job.id).scheduled_at
    assert await worker.run_once() is True
    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "failed"
    assert snapshot.attempt_count == 2


@pytest.mark.asyncio
async def test_concurrent_workers_execute_a_job_once(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store)
    registry = JobRegistry()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def handler(context, payload):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return JobOutcome(status="completed", result={})

    registry.register("test.echo", handler)
    first = asyncio.create_task(make_worker(worker_session_factory, registry, worker_id="one").run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    second = asyncio.create_task(make_worker(worker_session_factory, registry, worker_id="two").run_once())
    assert await asyncio.wait_for(second, timeout=1) is False
    release.set()
    assert await asyncio.wait_for(first, timeout=1) is True
    assert calls == 1
    assert store.get_for_owner(owner_id="user-a", job_id=job.id).status == "completed"


@pytest.mark.asyncio
async def test_worker_does_not_hold_a_database_session_across_handler_await(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'single-connection.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
        future=True,
    )
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        db.add(User(id="user-a", email="a@example.com", password_hash="hash"))
        db.commit()
    store = JobStore(factory)
    job = enqueue(store)
    registry = JobRegistry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(context, payload):
        started.set()
        await release.wait()
        return JobOutcome(status="completed", result={})

    registry.register("test.echo", handler)
    task = asyncio.create_task(make_worker(factory, registry).run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    try:
        snapshot = await asyncio.wait_for(
            asyncio.to_thread(store.get_for_owner, owner_id="user-a", job_id=job.id),
            timeout=0.5,
        )
        assert snapshot.status == "running"
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=1)
        engine.dispose()


@pytest.mark.asyncio
async def test_run_once_cancellation_propagates_and_cleans_up_heartbeat(worker_session_factory):
    store = JobStore(worker_session_factory)
    job = enqueue(store, scheduled_at=None)
    registry = JobRegistry()
    started = asyncio.Event()
    handler_cancelled = asyncio.Event()

    async def handler(context, payload):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            handler_cancelled.set()

    registry.register("test.echo", handler)
    worker = JobWorker(
        store=store,
        registry=registry,
        worker_id="cancelled-worker",
        lease_seconds=1,
        heartbeat_interval=0.02,
    )
    task = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert handler_cancelled.is_set()
    snapshot = store.get_for_owner(owner_id="user-a", job_id=job.id)
    assert snapshot.status == "running"
    assert snapshot.safe_error_code is None
    events_before = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    await asyncio.sleep(0.06)
    events_after = store.list_events_for_owner(owner_id="user-a", job_id=job.id)
    assert events_after == events_before


@pytest.mark.asyncio
async def test_managed_loop_stops_cleanly(worker_session_factory):
    registry = JobRegistry()
    stop = asyncio.Event()
    sleeps = 0

    async def fake_sleep(delay):
        nonlocal sleeps
        sleeps += 1
        stop.set()

    worker = make_worker(worker_session_factory, registry, sleep=fake_sleep)
    await worker.run(stop_event=stop, poll_interval=0.1)
    assert sleeps == 1
