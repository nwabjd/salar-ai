import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import Job, JobEvent, Workspace, token_id, utcnow
from .contracts import CLAIMABLE_STATUSES, ClaimedJob, JobOutcome, JobSnapshot


GENERIC_ERROR_CODE = "job_execution_failed"
GENERIC_ERROR_DETAIL = "The job could not be completed."
_VETTED_ERROR_DETAILS = MappingProxyType(
    {
        "provider_unavailable": "Please try again later.",
        "job_execution_failed": GENERIC_ERROR_DETAIL,
        "invalid_job_payload": "The job payload is invalid.",
        "unknown_job_kind": "This job type is unavailable.",
        "unsupported_workflow_action": "This workflow action is unsupported.",
    }
)


def retry_delay_seconds(
    job_id: str,
    attempt_count: int,
    retry_base_seconds: int = 5,
    retry_max_seconds: int = 300,
) -> int:
    base = min(retry_max_seconds, retry_base_seconds * (2 ** max(0, attempt_count - 1)))
    jitter = int(hashlib.sha256(job_id.encode()).hexdigest()[:4], 16) % max(1, base // 5)
    return base + jitter


def _utc(value: Optional[datetime] = None) -> datetime:
    value = utcnow() if value is None else value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decoded_object(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _is_encoded_object(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return isinstance(json.loads(value), dict)
    except (TypeError, ValueError):
        return False


def _sanitize_error(code: Any, _caller_detail: Any) -> tuple:
    candidate = code.strip().lower() if isinstance(code, str) else GENERIC_ERROR_CODE
    normalized_code = candidate if candidate in _VETTED_ERROR_DETAILS else GENERIC_ERROR_CODE
    return normalized_code, _VETTED_ERROR_DETAILS[normalized_code]


class JobStore:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def enqueue(
        self,
        *,
        owner_id: str,
        kind: str,
        input_data: Dict[str, Any],
        idempotency_key: str,
        workspace_id: Optional[str] = None,
        priority: int = 100,
        scheduled_at: Optional[datetime] = None,
        max_attempts: int = 3,
    ) -> JobSnapshot:
        if not isinstance(input_data, dict):
            raise ValueError("Job input must be an object")
        if not kind:
            raise ValueError("Job kind must be non-empty")
        if not idempotency_key:
            raise ValueError("Idempotency key must be non-empty")
        if max_attempts < 1:
            raise ValueError("Maximum attempts must be at least one")

        with self.session_factory() as db:
            existing = self._find_idempotent(db, owner_id, idempotency_key)
            if existing is not None:
                return self._snapshot(existing)
            if workspace_id is not None:
                workspace = db.execute(
                    select(Workspace.id).where(Workspace.id == workspace_id, Workspace.user_id == owner_id)
                ).scalar_one_or_none()
                if workspace is None:
                    raise ValueError("Workspace does not belong to owner")
            now = _utc()
            job = Job(
                owner_id=owner_id,
                workspace_id=workspace_id,
                kind=kind,
                status="queued",
                priority=priority,
                input_json=json.dumps(input_data),
                progress=0.0,
                scheduled_at=_utc(scheduled_at) if scheduled_at is not None else now,
                attempt_count=0,
                max_attempts=max_attempts,
                idempotency_key=idempotency_key,
                created_at=now,
                updated_at=now,
            )
            db.add(job)
            try:
                db.flush()
                self._append_event(db, job.id, "job.queued", {"scheduled_at": job.scheduled_at.isoformat()}, now)
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = self._find_idempotent(db, owner_id, idempotency_key)
                if existing is None:
                    raise
                return self._snapshot(existing)
            return self._snapshot(job)

    def get_for_owner(self, *, owner_id: str, job_id: str) -> Optional[JobSnapshot]:
        with self.session_factory() as db:
            job = db.execute(select(Job).where(Job.id == job_id, Job.owner_id == owner_id)).scalar_one_or_none()
            return None if job is None else self._snapshot(job)

    def list_for_owner(
        self,
        *,
        owner_id: str,
        workspace_id: Optional[str] = None,
        statuses: Optional[Iterable[str]] = None,
        limit: int = 50,
        before: Optional[datetime] = None,
    ) -> List[JobSnapshot]:
        with self.session_factory() as db:
            query = select(Job).where(Job.owner_id == owner_id)
            if workspace_id is not None:
                query = query.where(Job.workspace_id == workspace_id)
            if statuses is not None:
                status_values = tuple(statuses)
                if not status_values:
                    return []
                query = query.where(Job.status.in_(status_values))
            if before is not None:
                query = query.where(Job.created_at < _utc(before))
            jobs = db.execute(
                query.order_by(Job.created_at.desc(), Job.id.desc()).limit(max(1, min(int(limit), 200)))
            ).scalars()
            return [self._snapshot(job) for job in jobs]

    def list_events_for_owner(
        self,
        *,
        owner_id: str,
        job_id: str,
        after_sequence: int = 0,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self.session_factory() as db:
            events = db.execute(
                select(JobEvent)
                .join(Job, Job.id == JobEvent.job_id)
                .where(
                    Job.owner_id == owner_id,
                    Job.id == job_id,
                    JobEvent.sequence > after_sequence,
                )
                .order_by(JobEvent.sequence.asc())
                .limit(max(1, min(int(limit), 500)))
            ).scalars()
            return [
                {
                    "sequence": event.sequence,
                    "event_type": event.event_type,
                    "payload": _decoded_object(event.payload_json) or {},
                    "created_at": _utc(event.created_at),
                }
                for event in events
            ]

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        now: Optional[datetime] = None,
    ) -> Optional[ClaimedJob]:
        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive")
        claimed_at = _utc(now)
        for _ in range(100):
            with self.session_factory() as db:
                candidate = db.execute(
                    select(Job.id, Job.input_json)
                    .where(
                        Job.status.in_(CLAIMABLE_STATUSES),
                        Job.scheduled_at <= claimed_at,
                        Job.cancel_requested_at.is_(None),
                        or_(Job.lease_token.is_(None), Job.lease_expires_at <= claimed_at),
                    )
                    .order_by(Job.priority.asc(), Job.scheduled_at.asc(), Job.created_at.asc(), Job.id.asc())
                    .limit(1)
                ).first()
                if candidate is None:
                    return None
                candidate_id, input_json = candidate
                if not _is_encoded_object(input_json):
                    result = db.execute(
                        update(Job)
                        .where(
                            Job.id == candidate_id,
                            Job.input_json == input_json,
                            Job.status.in_(CLAIMABLE_STATUSES),
                            Job.scheduled_at <= claimed_at,
                            Job.cancel_requested_at.is_(None),
                            or_(Job.lease_token.is_(None), Job.lease_expires_at <= claimed_at),
                        )
                        .values(
                            status="failed",
                            safe_error_code="invalid_job_input",
                            safe_error_detail="The job input could not be read.",
                            lease_token=None,
                            lease_expires_at=None,
                            finished_at=claimed_at,
                            updated_at=claimed_at,
                        )
                        .execution_options(synchronize_session=False)
                    )
                    if result.rowcount != 1:
                        db.rollback()
                        continue
                    self._append_event(
                        db,
                        candidate_id,
                        "job.failed",
                        {"code": "invalid_job_input", "detail": "The job input could not be read."},
                        claimed_at,
                    )
                    db.commit()
                    continue
                lease_token = token_id()
                lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)
                result = db.execute(
                    update(Job)
                    .where(
                        Job.id == candidate_id,
                        Job.input_json == input_json,
                        Job.status.in_(CLAIMABLE_STATUSES),
                        Job.scheduled_at <= claimed_at,
                        Job.cancel_requested_at.is_(None),
                        or_(Job.lease_token.is_(None), Job.lease_expires_at <= claimed_at),
                    )
                    .values(
                        status="running",
                        lease_token=lease_token,
                        lease_expires_at=lease_expires_at,
                        attempt_count=Job.attempt_count + 1,
                        started_at=case((Job.started_at.is_(None), claimed_at), else_=Job.started_at),
                        updated_at=claimed_at,
                    )
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount != 1:
                    db.rollback()
                    continue
                job = db.get(Job, candidate_id)
                self._append_event(
                    db,
                    job.id,
                    "job.claimed",
                    {"worker_id": worker_id, "attempt": job.attempt_count},
                    claimed_at,
                )
                db.commit()
                return self._claimed_snapshot(job)
        return None

    def heartbeat(
        self,
        *,
        job_id: str,
        lease_token: str,
        lease_seconds: int,
        now: Optional[datetime] = None,
    ) -> bool:
        if lease_seconds <= 0:
            raise ValueError("Lease duration must be positive")
        heartbeat_at = _utc(now)
        with self.session_factory() as db:
            result = db.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.lease_token == lease_token,
                    Job.lease_expires_at > heartbeat_at,
                )
                .values(
                    lease_expires_at=heartbeat_at + timedelta(seconds=lease_seconds),
                    updated_at=heartbeat_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.rollback()
                return False
            db.commit()
            return True

    def record_progress(
        self,
        *,
        job_id: str,
        lease_token: str,
        progress: float,
        event_type: str,
        payload: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("Progress payload must be an object")
        if not event_type:
            raise ValueError("Progress event type must be non-empty")
        progress_value = max(0.0, min(float(progress), 1.0))
        progress_at = _utc(now)
        with self.session_factory() as db:
            result = db.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.lease_token == lease_token,
                    Job.lease_expires_at > progress_at,
                )
                .values(
                    progress=case((Job.progress < progress_value, progress_value), else_=Job.progress),
                    updated_at=progress_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.rollback()
                return False
            self._append_event(db, job_id, event_type, payload, progress_at)
            db.commit()
            return True

    def request_cancel(
        self,
        *,
        owner_id: str,
        job_id: str,
        now: Optional[datetime] = None,
    ) -> Optional[JobSnapshot]:
        requested_at = _utc(now)
        for _ in range(3):
            with self.session_factory() as db:
                job = db.execute(
                    select(Job).where(Job.id == job_id, Job.owner_id == owner_id)
                ).scalar_one_or_none()
                if job is None:
                    return None
                if job.status in CLAIMABLE_STATUSES:
                    result = db.execute(
                        update(Job)
                        .where(Job.id == job_id, Job.owner_id == owner_id, Job.status == job.status)
                        .values(
                            status="cancelled",
                            cancel_requested_at=requested_at,
                            finished_at=requested_at,
                            lease_token=None,
                            lease_expires_at=None,
                            updated_at=requested_at,
                        )
                        .execution_options(synchronize_session=False)
                    )
                    event_type = "job.cancelled"
                elif job.status == "running" and job.cancel_requested_at is None:
                    result = db.execute(
                        update(Job)
                        .where(
                            Job.id == job_id,
                            Job.owner_id == owner_id,
                            Job.status == "running",
                            Job.cancel_requested_at.is_(None),
                        )
                        .values(cancel_requested_at=requested_at, updated_at=requested_at)
                        .execution_options(synchronize_session=False)
                    )
                    event_type = "job.cancel_requested"
                else:
                    return self._snapshot(job)
                if result.rowcount != 1:
                    db.rollback()
                    continue
                self._append_event(db, job_id, event_type, {}, requested_at)
                db.commit()
                db.expire_all()
                refreshed = db.get(Job, job_id)
                return self._snapshot(refreshed)
        return self.get_for_owner(owner_id=owner_id, job_id=job_id)

    def is_cancel_requested(self, *, job_id: str, lease_token: str) -> bool:
        with self.session_factory() as db:
            return bool(
                db.execute(
                    select(Job.id).where(
                        Job.id == job_id,
                        Job.status == "running",
                        Job.lease_token == lease_token,
                        Job.cancel_requested_at.is_not(None),
                    )
                ).scalar_one_or_none()
            )

    def complete(
        self,
        *,
        job_id: str,
        lease_token: str,
        outcome: JobOutcome,
        now: Optional[datetime] = None,
    ) -> bool:
        if not isinstance(outcome, JobOutcome):
            raise ValueError("Outcome must be a JobOutcome")
        completed_at = _utc(now)
        with self.session_factory() as db:
            if self._finalize_cancel_requested(db, job_id, lease_token, completed_at):
                db.commit()
                return False
            result = db.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.lease_token == lease_token,
                    Job.lease_expires_at > completed_at,
                    Job.cancel_requested_at.is_(None),
                )
                .values(
                    status=outcome.status,
                    result_json=json.dumps(outcome.result),
                    progress=1.0,
                    safe_error_code=None,
                    safe_error_detail=None,
                    lease_token=None,
                    lease_expires_at=None,
                    finished_at=completed_at,
                    updated_at=completed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                if self._finalize_cancel_requested(db, job_id, lease_token, completed_at):
                    db.commit()
                    return False
                db.rollback()
                return False
            self._append_event(db, job_id, f"job.{outcome.status}", {"result": outcome.result}, completed_at)
            db.commit()
            return True

    def fail_or_retry(
        self,
        *,
        job_id: str,
        lease_token: str,
        code: Any,
        safe_detail: Any,
        now: Optional[datetime] = None,
    ) -> str:
        failed_at = _utc(now)
        safe_code, safe_message = _sanitize_error(code, safe_detail)
        with self.session_factory() as db:
            if self._finalize_cancel_requested(db, job_id, lease_token, failed_at):
                db.commit()
                return "cancelled"
            job = db.execute(
                select(Job).where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.lease_token == lease_token,
                    Job.lease_expires_at > failed_at,
                    Job.cancel_requested_at.is_(None),
                )
            ).scalar_one_or_none()
            if job is None:
                if self._finalize_cancel_requested(db, job_id, lease_token, failed_at):
                    db.commit()
                    return "cancelled"
                return "stale"
            exhausted = job.attempt_count >= job.max_attempts
            status = "failed" if exhausted else "retrying"
            scheduled_at = (
                job.scheduled_at
                if exhausted
                else failed_at + timedelta(seconds=retry_delay_seconds(job.id, job.attempt_count))
            )
            result = db.execute(
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running",
                    Job.lease_token == lease_token,
                    Job.lease_expires_at > failed_at,
                    Job.cancel_requested_at.is_(None),
                )
                .values(
                    status=status,
                    safe_error_code=safe_code,
                    safe_error_detail=safe_message,
                    scheduled_at=scheduled_at,
                    lease_token=None,
                    lease_expires_at=None,
                    finished_at=failed_at if exhausted else None,
                    updated_at=failed_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                if self._finalize_cancel_requested(db, job_id, lease_token, failed_at):
                    db.commit()
                    return "cancelled"
                db.rollback()
                return "stale"
            payload = {"code": safe_code, "detail": safe_message}
            if not exhausted:
                payload["scheduled_at"] = _utc(scheduled_at).isoformat()
            self._append_event(db, job_id, f"job.{status}", payload, failed_at)
            db.commit()
            return status

    def recover_abandoned(self, *, now: Optional[datetime] = None) -> int:
        recovered_at = _utc(now)
        recovered = 0
        with self.session_factory() as db:
            jobs = list(
                db.execute(
                    select(Job).where(
                        Job.status == "running",
                        Job.lease_token.is_not(None),
                        Job.lease_expires_at <= recovered_at,
                    )
                ).scalars()
            )
            for job in jobs:
                cancelled = job.cancel_requested_at is not None
                exhausted = job.attempt_count >= job.max_attempts
                status = "cancelled" if cancelled else ("failed" if exhausted else "retrying")
                values = {
                    "status": status,
                    "scheduled_at": recovered_at,
                    "lease_token": None,
                    "lease_expires_at": None,
                    "updated_at": recovered_at,
                }
                if cancelled:
                    values["finished_at"] = recovered_at
                elif exhausted:
                    values.update(
                        safe_error_code="job_lease_expired",
                        safe_error_detail="The worker lease expired before the job completed.",
                        finished_at=recovered_at,
                    )
                result = db.execute(
                    update(Job)
                    .where(
                        Job.id == job.id,
                        Job.status == "running",
                        Job.lease_token == job.lease_token,
                        Job.lease_expires_at <= recovered_at,
                        Job.cancel_requested_at.is_not(None)
                        if cancelled
                        else Job.cancel_requested_at.is_(None),
                    )
                    .values(**values)
                    .execution_options(synchronize_session=False)
                )
                if result.rowcount != 1:
                    continue
                event_payload = {"code": "job_lease_expired"} if exhausted and not cancelled else {}
                self._append_event(db, job.id, f"job.{status}", event_payload, recovered_at)
                recovered += 1
            db.commit()
        return recovered

    def _finalize_cancel_requested(
        self,
        db: Session,
        job_id: str,
        lease_token: str,
        finalized_at: datetime,
    ) -> bool:
        result = db.execute(
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "running",
                Job.lease_token == lease_token,
                Job.lease_expires_at > finalized_at,
                Job.cancel_requested_at.is_not(None),
            )
            .values(
                status="cancelled",
                lease_token=None,
                lease_expires_at=None,
                finished_at=finalized_at,
                updated_at=finalized_at,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return False
        self._append_event(db, job_id, "job.cancelled", {}, finalized_at)
        return True

    @staticmethod
    def _find_idempotent(db: Session, owner_id: str, idempotency_key: str) -> Optional[Job]:
        return db.execute(
            select(Job).where(Job.owner_id == owner_id, Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()

    @staticmethod
    def _append_event(
        db: Session,
        job_id: str,
        event_type: str,
        payload: Dict[str, Any],
        created_at: datetime,
    ) -> None:
        for attempt in range(3):
            sequence = db.execute(
                select(func.coalesce(func.max(JobEvent.sequence), 0) + 1).where(JobEvent.job_id == job_id)
            ).scalar_one()
            try:
                with db.begin_nested():
                    db.add(
                        JobEvent(
                            job_id=job_id,
                            sequence=sequence,
                            event_type=event_type,
                            payload_json=json.dumps(payload),
                            created_at=created_at,
                        )
                    )
                    db.flush()
                return
            except IntegrityError:
                if attempt == 2:
                    raise

    @staticmethod
    def _snapshot_values(job: Job) -> Dict[str, Any]:
        return {
            "id": job.id,
            "owner_id": job.owner_id,
            "workspace_id": job.workspace_id,
            "workflow_run_id": job.workflow_run_id,
            "kind": job.kind,
            "status": job.status,
            "priority": job.priority,
            "input_data": _decoded_object(job.input_json) or {},
            "result": _decoded_object(job.result_json),
            "safe_error_code": job.safe_error_code,
            "safe_error_detail": job.safe_error_detail,
            "progress": job.progress,
            "scheduled_at": _utc(job.scheduled_at),
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "idempotency_key": job.idempotency_key,
            "cancel_requested_at": None if job.cancel_requested_at is None else _utc(job.cancel_requested_at),
            "created_at": _utc(job.created_at),
            "started_at": None if job.started_at is None else _utc(job.started_at),
            "finished_at": None if job.finished_at is None else _utc(job.finished_at),
            "updated_at": _utc(job.updated_at),
        }

    @classmethod
    def _snapshot(cls, job: Job) -> JobSnapshot:
        return JobSnapshot(**cls._snapshot_values(job))

    @classmethod
    def _claimed_snapshot(cls, job: Job) -> ClaimedJob:
        return ClaimedJob(
            **cls._snapshot_values(job),
            lease_token=job.lease_token,
            lease_expires_at=_utc(job.lease_expires_at),
        )
