import asyncio

from app.config import Settings
from app.database import Base, create_session_factory
from app.models import User
from app.services.jobs.contracts import JobRegistry
from app.services.jobs.store import JobStore
from app.services.jobs.worker import JobWorker


def _make_worker(session_factory, registry):
    return JobWorker(
        session_factory=session_factory,
        settings=Settings(),
        registry=registry,
        poll_interval=0.05,
        lease_seconds=60,
    )


def test_worker_runs_registered_handler_to_completion(tmp_path):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'worker-ok.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="worker-ok@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            user_id = user.id
            job = JobStore(db).enqueue(user_id=user_id, kind="test.echo", input_data={"value": 42})
            job_id = job.id
            db.commit()

        registry = JobRegistry()

        @registry.register("test.echo")
        async def echo(ctx):
            assert ctx.user_id == user_id
            return {"echo": ctx.input_data["value"]}

        async def run():
            worker = _make_worker(session_factory, registry)
            await worker._poll_once()
            if worker._inflight:
                await asyncio.gather(*list(worker._inflight))
            await worker.stop()

        asyncio.run(run())

        with session_factory() as db:
            saved = db.get(job.__class__, job_id)
            assert saved.status == "completed"
    finally:
        engine.dispose()


def test_worker_marks_failed_job_and_requeues_with_retries(tmp_path):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'worker-fail.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="worker-fail@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            user_id = user.id
            job = JobStore(db).enqueue(user_id=user_id, kind="test.boom", max_attempts=2)
            job_id = job.id
            db.commit()

        registry = JobRegistry()

        @registry.register("test.boom")
        async def boom(ctx):
            raise RuntimeError("kaboom")

        async def run():
            worker = _make_worker(session_factory, registry)
            await worker._poll_once()
            if worker._inflight:
                await asyncio.gather(*list(worker._inflight))
            await worker.stop()

        asyncio.run(run())

        with session_factory() as db:
            saved = db.get(job.__class__, job_id)
            assert saved.status == "queued"
            assert saved.attempts == 1
            assert "kaboom" in saved.error
    finally:
        engine.dispose()


def test_worker_unknown_kind_fails_without_retry(tmp_path):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'worker-ghost.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="worker-ghost@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            user_id = user.id
            job = JobStore(db).enqueue(user_id=user_id, kind="test.ghost")
            job_id = job.id
            db.commit()

        async def run():
            worker = _make_worker(session_factory, JobRegistry())
            await worker._poll_once()
            if worker._inflight:
                await asyncio.gather(*list(worker._inflight))
            await worker.stop()

        asyncio.run(run())

        with session_factory() as db:
            saved = db.get(job.__class__, job_id)
            assert saved.status == "failed"
            assert "unknown" in saved.error
    finally:
        engine.dispose()
