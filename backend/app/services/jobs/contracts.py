from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Optional


TERMINAL_STATUSES = frozenset({"completed", "partial", "failed", "cancelled", "expired"})
CLAIMABLE_STATUSES = frozenset({"queued", "retrying"})


@dataclass(frozen=True)
class JobOutcome:
    status: Literal["completed", "partial"]
    result: Dict[str, Any]

    def __post_init__(self) -> None:
        if self.status not in {"completed", "partial"}:
            raise ValueError("Job outcome status must be completed or partial")
        if not isinstance(self.result, dict):
            raise ValueError("Job outcome result must be an object")


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    owner_id: str
    workspace_id: Optional[str]
    workflow_run_id: Optional[str]
    kind: str
    status: str
    priority: int
    input_data: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    safe_error_code: Optional[str]
    safe_error_detail: Optional[str]
    progress: float
    scheduled_at: datetime
    attempt_count: int
    max_attempts: int
    idempotency_key: str
    cancel_requested_at: Optional[datetime]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    updated_at: datetime


@dataclass(frozen=True)
class ClaimedJob(JobSnapshot):
    lease_token: str
    lease_expires_at: datetime


class RetryableJobError(Exception):
    def __init__(self, code: str, safe_detail: str):
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


class PermanentJobError(Exception):
    def __init__(self, code: str, safe_detail: str):
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


class JobCancelled(Exception):
    pass
