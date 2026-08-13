"""Durable job store — enqueue, lease, heartbeat, progress, and compare-and-set terminal writes."""

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...models import Job, JobEvent, token_id

log = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _next_sequence(db: Session, job_id: str) -> int:
    value = db.scalar(select(func.count(JobEvent.id)).where(JobEvent.job_id == job_id))
    return int(value or 0) + 1


class JobStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- writes ----

    def enqueue(
        self,
        *,
        user_id: str,
        kind: str,
        input_data: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        max_attempts: int = 3,
        job_id: Optional[str] = None,
        workflow_run_id: Optional[str] = None,
    ) -> Job:
        job = Job(
            id=job_id or token_id(),
            user_id=user_id,
            kind=kind,
            priority=priority,
            input_json=json.dumps(input_data or {}),
            scheduled_at=scheduled_at,
            max_attempts=max_attempts,
            workflow_run_id=workflow_run_id,
        )
        self.db.add(job)
        self.db.flush()
        self._step(job, "enqueue", "queued", detail={"priority": priority, "scheduled_at": str(scheduled_at) if scheduled_at else None})
        return job

    def has_pending(self, user_id: str, kind: str) -> bool:
        row = self.db.scalar(
            select(func.count(Job.id)).where(
                Job.user_id == user_id,
                Job.kind == kind,
                Job.status.in_(("queued", "running")),
            )
        )
        return int(row or 0) > 0

    def claim(self, *, worker_id: str, now: Optional[datetime] = None, limit: int = 5) -> List[Tuple[Job, str]]:
        now = now or utcnow()
        candidates = self.db.scalars(
            select(Job)
            .where(
                Job.status == "queued",
                or_(Job.scheduled_at.is_(None), Job.scheduled_at <= now),
                or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now),
                or_(Job.next_attempt_at.is_(None), Job.next_attempt_at <= now),
            )
            .order_by(Job.priority.asc(), Job.created_at.asc())
            .limit(limit)
        ).all()

        claimed: List[Tuple[Job, str]] = []
        for job in candidates:
            lease = secrets.token_urlsafe(32)
            job.status = "running"
            job.lease_token = lease
            job.lease_expires_at = now + timedelta(seconds=120)
            job.started_at = now
            job.attempts += 1
            self._step(job, "claim", "running", detail={"worker": worker_id, "attempt": job.attempts})
            claimed.append((job, lease))
        if claimed:
            self.db.commit()
        return claimed

    def heartbeat(self, job: Job, lease_token: str, expires_at: datetime) -> bool:
        if job.lease_token != lease_token:
            return False
        job.lease_expires_at = expires_at
        return True

    def progress(self, job: Job, lease_token: str, name: str, detail: Optional[Dict[str, Any]] = None) -> bool:
        if job.lease_token != lease_token:
            return False
        self._step(job, name, "running", detail=detail)
        return True

    def complete(self, job: Job, lease_token: str, output: Optional[Dict[str, Any]] = None) -> bool:
        if job.lease_token != lease_token or job.status not in ("running",):
            return False
        job.status = "completed"
        job.output_json = json.dumps(output or {})
        job.finished_at = utcnow()
        job.lease_token = None
        job.lease_expires_at = None
        self._step(job, "complete", "completed", detail={"output_keys": sorted((output or {}).keys())})
        self.db.commit()
        return True

    def fail(
        self,
        job: Job,
        lease_token: str,
        error: str,
        *,
        retry: bool = True,
        attempt: Optional[int] = None,
    ) -> bool:
        if job.lease_token != lease_token:
            return False
        now = utcnow()
        job.error = (error or "")[:2000]
        attempt = attempt or job.attempts
        if retry and job.attempts < job.max_attempts:
            backoff = self._backoff(attempt)
            job.status = "queued"
            job.next_attempt_at = now + backoff
            job.lease_token = None
            job.lease_expires_at = None
            job.finished_at = None
            self._step(job, "fail", "queued", detail={"error": job.error[:1000], "retry_at": str(job.next_attempt_at)})
            self.db.commit()
            return True
        job.status = "failed"
        job.finished_at = now
        job.lease_token = None
        job.lease_expires_at = None
        self._step(job, "fail", "failed", detail={"error": job.error[:1000], "attempts": attempt})
        self.db.commit()
        return True

    def cancel(self, job_id: str, user_id: str) -> bool:
        job = self.db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
        if job is None or job.status in TERMINAL_STATUSES:
            return False
        job.status = "cancelled"
        job.finished_at = utcnow()
        job.lease_token = None
        job.lease_expires_at = None
        self._step(job, "cancel", "cancelled")
        self.db.commit()
        return True

    # ---- reads ----

    def get(self, job_id: str) -> Optional[Job]:
        return self.db.get(Job, job_id)

    def list_for_user(self, user_id: str, *, limit: int = 50, kinds: Optional[Sequence[str]] = None) -> List[Job]:
        statement = select(Job).where(Job.user_id == user_id)
        if kinds:
            statement = statement.where(Job.kind.in_(kinds))
        statement = statement.order_by(Job.created_at.desc()).limit(limit)
        return list(self.db.scalars(statement).all())

    def events(self, job_id: str, *, limit: int = 200) -> List[JobEvent]:
        return list(
            self.db.scalars(
                select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.sequence.asc()).limit(limit)
            )
        )

    # ---- internals ----

    def _step(self, job: Job, name: str, status: str, detail: Optional[Dict[str, Any]] = None) -> None:
        self.db.add(
            JobEvent(
                job_id=job.id,
                sequence=_next_sequence(self.db, job.id),
                name=name,
                status=status,
                detail_json=json.dumps(detail or {}),
            )
        )

    @staticmethod
    def _backoff(attempt: int) -> timedelta:
        base = min(60, 2 ** max(1, attempt - 1))
        return timedelta(seconds=base)
