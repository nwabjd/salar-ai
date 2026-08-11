import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from .contracts import (
    ClaimedJob,
    JobCancelled,
    JobOutcome,
    PermanentJobError,
    RetryableJobError,
)
from .registry import JobRegistry
from .store import JobStore


logger = logging.getLogger(__name__)


class JobLeaseLost(Exception):
    pass


class JobExecutionContext:
    def __init__(
        self,
        *,
        store: JobStore,
        claim: ClaimedJob,
        lease_seconds: float,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._lease_token = claim.lease_token
        self._lease_seconds = lease_seconds
        self._clock = clock
        self.job_id = claim.id
        self.owner_id = claim.owner_id
        self.workspace_id = claim.workspace_id

    async def progress(
        self,
        progress: float,
        payload: Optional[Dict[str, Any]] = None,
        event_type: str = "job.progress",
    ) -> None:
        recorded = self._store.record_progress(
            job_id=self.job_id,
            lease_token=self._lease_token,
            progress=progress,
            event_type=event_type,
            payload={} if payload is None else payload,
            now=self._clock(),
        )
        if not recorded:
            raise JobLeaseLost("The job lease is no longer owned by this execution")

    async def raise_if_cancelled(self) -> None:
        state = self._store.lease_state(
            job_id=self.job_id,
            lease_token=self._lease_token,
            now=self._clock(),
        )
        if state == "cancel_requested":
            raise JobCancelled()
        if state != "active":
            raise JobLeaseLost("The job lease is no longer owned by this execution")

    async def request_approval(self, action_kind: str, preview: Dict[str, Any]) -> None:
        raise NotImplementedError("Job approvals are unsupported until Task 3")

    async def fence_external_action(self) -> None:
        state = self._store.fence_external_action(
            job_id=self.job_id,
            lease_token=self._lease_token,
            lease_seconds=self._lease_seconds,
            now=self._clock(),
        )
        if state == "cancel_requested":
            raise JobCancelled()
        if state != "active":
            raise JobLeaseLost("The job lease is no longer owned by this execution")


class JobWorker:
    def __init__(
        self,
        *,
        store: JobStore,
        registry: JobRegistry,
        worker_id: str,
        lease_seconds: float = 30,
        heartbeat_interval: Optional[float] = None,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 300,
        clock: Optional[Callable[[], datetime]] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive")
        interval = lease_seconds / 4 if heartbeat_interval is None else heartbeat_interval
        if interval <= 0 or interval >= lease_seconds / 3:
            raise ValueError("Heartbeat interval must be positive and less than one third of the lease")
        if retry_base_seconds <= 0 or retry_max_seconds <= 0:
            raise ValueError("Retry delays must be positive")
        self.store = store
        self.registry = registry
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.heartbeat_interval = interval
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep

    async def run_once(self) -> bool:
        self.store.recover_abandoned(now=self.clock())
        claim = self.store.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
            now=self.clock(),
        )
        if claim is None:
            return False

        handler = self.registry.resolve(claim.kind)
        if handler is None:
            self.store.fail_terminal(
                job_id=claim.id,
                lease_token=claim.lease_token,
                code="unknown_job_kind",
                safe_detail="",
                now=self.clock(),
            )
            return True

        context = JobExecutionContext(
            store=self.store,
            claim=claim,
            lease_seconds=self.lease_seconds,
            clock=self.clock,
        )
        ownership_lost = asyncio.Event()
        handler_task = asyncio.create_task(handler(context, claim.input_data))
        heartbeat_task = asyncio.create_task(
            self._heartbeat(claim=claim, handler_task=handler_task, ownership_lost=ownership_lost)
        )
        disposition = "outcome"
        value: Any = None
        try:
            value = await handler_task
        except asyncio.CancelledError:
            if ownership_lost.is_set():
                disposition = "stale"
            else:
                raise
        except JobCancelled:
            disposition = "cancelled"
        except JobLeaseLost:
            disposition = "stale"
        except RetryableJobError as error:
            disposition = "retryable"
            value = error
        except PermanentJobError as error:
            disposition = "permanent"
            value = error
        except Exception:
            logger.exception("Background job %s failed unexpectedly", claim.id)
            disposition = "unexpected"
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

        if ownership_lost.is_set() or disposition == "stale":
            return True

        state = self.store.lease_state(
            job_id=claim.id,
            lease_token=claim.lease_token,
            now=self.clock(),
        )
        if state == "stale":
            return True
        if state == "cancel_requested" or disposition == "cancelled":
            self.store.acknowledge_cancel(
                job_id=claim.id,
                lease_token=claim.lease_token,
                now=self.clock(),
            )
            return True

        if disposition == "retryable":
            self.store.fail_or_retry(
                job_id=claim.id,
                lease_token=claim.lease_token,
                code=value.code,
                safe_detail=value.safe_detail,
                now=self.clock(),
                retry_base_seconds=self.retry_base_seconds,
                retry_max_seconds=self.retry_max_seconds,
            )
        elif disposition == "permanent":
            self.store.fail_terminal(
                job_id=claim.id,
                lease_token=claim.lease_token,
                code=value.code,
                safe_detail=value.safe_detail,
                now=self.clock(),
            )
        elif disposition == "unexpected":
            self.store.fail_or_retry(
                job_id=claim.id,
                lease_token=claim.lease_token,
                code="job_execution_failed",
                safe_detail="",
                now=self.clock(),
                retry_base_seconds=self.retry_base_seconds,
                retry_max_seconds=self.retry_max_seconds,
            )
        elif isinstance(value, JobOutcome):
            self.store.complete(
                job_id=claim.id,
                lease_token=claim.lease_token,
                outcome=value,
                now=self.clock(),
            )
        else:
            logger.error("Background job %s returned an invalid outcome", claim.id)
            self.store.fail_or_retry(
                job_id=claim.id,
                lease_token=claim.lease_token,
                code="job_execution_failed",
                safe_detail="",
                now=self.clock(),
                retry_base_seconds=self.retry_base_seconds,
                retry_max_seconds=self.retry_max_seconds,
            )
        return True

    async def _heartbeat(
        self,
        *,
        claim: ClaimedJob,
        handler_task: "asyncio.Task[JobOutcome]",
        ownership_lost: asyncio.Event,
    ) -> None:
        while True:
            await self.sleep(self.heartbeat_interval)
            try:
                renewed = self.store.heartbeat(
                    job_id=claim.id,
                    lease_token=claim.lease_token,
                    lease_seconds=self.lease_seconds,
                    now=self.clock(),
                )
            except Exception:
                logger.exception("Heartbeat failed for background job %s", claim.id)
                renewed = False
            if not renewed:
                ownership_lost.set()
                handler_task.cancel()
                return

    async def run(self, *, stop_event: asyncio.Event, poll_interval: float = 1.0) -> None:
        if poll_interval <= 0:
            raise ValueError("Poll interval must be positive")
        while not stop_event.is_set():
            worked = await self.run_once()
            if not worked and not stop_event.is_set():
                await self.sleep(poll_interval)
