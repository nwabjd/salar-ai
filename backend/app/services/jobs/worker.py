"""Lease-based background job worker.

The worker polls the store for due jobs, leases them (compare-and-set), and runs
the registered async handler. Heartbeats keep the lease alive while a long job is
in flight. On success the job is completed; on failure it is retried with backoff
up to max_attempts.

Run as a singleton per process. Multiple processes may run concurrently — the
lease fencing in JobStore.claim ensures no two workers run the same job.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ...config import Settings
from .contracts import JobContext, JobRegistry, normalize_error
from .store import JobStore, utcnow

log = logging.getLogger(__name__)


class JobWorker:
    def __init__(
        self,
        *,
        session_factory,
        settings: Settings,
        registry: JobRegistry,
        poll_interval: float = 5.0,
        lease_seconds: int = 120,
        claim_limit: int = 5,
        heartbeat_interval: float = 30.0,
        worker_id: Optional[str] = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.registry = registry
        self.poll_interval = poll_interval
        self.lease_seconds = lease_seconds
        self.claim_limit = claim_limit
        self.heartbeat_interval = heartbeat_interval
        self.worker_id = worker_id or f"worker-{id(self):x}"
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._inflight: set[asyncio.Task] = set()

    # ---- lifecycle ----

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("JobWorker %s started", self.worker_id)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._inflight:
            await asyncio.gather(*list(self._inflight), return_exceptions=True)

    # ---- loop ----

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("JobWorker poll error: %s", exc)
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        with self.session_factory() as db:
            store = JobStore(db)
            claimed = store.claim(worker_id=self.worker_id, limit=self.claim_limit)
        for job, lease_token in claimed:
            task = asyncio.create_task(self._execute(db_session=job.id, job=job, lease_token=lease_token))
            self._inflight.add(task)
            task.add_done_callback(self._inflight.discard)

    async def _execute(self, db_session, job, lease_token: str) -> None:
        handler = self.registry.get(job.kind)
        if handler is None:
            log.warning("No handler for job kind '%s' (%s)", job.kind, job.id)
            with self.session_factory() as db:
                fresh = db.get(job.__class__, job.id)
                if fresh is not None:
                    JobStore(db).fail(fresh, lease_token, f"unknown job kind '{job.kind}'", retry=False)
            return

        heartbeat_task = asyncio.create_task(self._heartbeat_loop(job, lease_token))
        try:
            with self.session_factory() as db:
                fresh = db.get(job.__class__, job.id)
                if fresh is None:
                    log.warning("Job %s vanished before execution", job.id)
                    return
                store = JobStore(db)
                ctx = JobContext(
                    user_id=fresh.user_id,
                    job_id=fresh.id,
                    kind=fresh.kind,
                    db=db,
                    settings=self.settings,
                    input_data=_load_json(fresh.input_json),
                )
                output = await handler(ctx)
                store.complete(fresh, lease_token, output=output)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("Job %s (%s) failed", job.id, job.kind)
            try:
                with self.session_factory() as db:
                    fresh = db.get(job.__class__, job.id)
                    if fresh is not None:
                        JobStore(db).fail(fresh, lease_token, normalize_error(exc))
            except Exception:
                log.exception("Could not persist failure for job %s", job.id)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, job, lease_token: str) -> None:
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                with self.session_factory() as db:
                    fresh = db.get(job.__class__, job.id)
                    if fresh is None:
                        return
                    expires = utcnow() + timedelta(seconds=self.lease_seconds)
                    if not JobStore(db).heartbeat(fresh, lease_token, expires):
                        log.warning("Job %s heartbeat rejected (lease lost)", job.id)
                        return
                    db.commit()
            except Exception as exc:
                log.warning("Job %s heartbeat error: %s", job.id, exc)


def _load_json(raw: str) -> dict:
    import json

    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}
