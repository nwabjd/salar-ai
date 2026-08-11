# SALAR Durable Background Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SALAR's instant-success workflow placeholders with a durable, owner-scoped job engine that supports scheduling, progress, cancellation, retries, approvals, restart recovery, and a focused Jobs UI.

**Architecture:** Add an append-only event ledger around a compare-and-set leased `Job` record. A short-session `JobStore` owns all persistence, an async worker owns handler execution without holding database sessions across awaits, and a scheduler converts due definitions into idempotent jobs. Existing workflows enqueue `workflow.execute` jobs and retain `WorkflowRun` as a compatibility projection. The web/PWA polls a narrow authenticated API for user-visible status and approvals.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2, SQLite/Postgres-compatible SQL, asyncio, Pydantic settings, pytest/pytest-asyncio, React, TypeScript, Vitest, Vite.

---

## Delivery and branch policy

- Execute in an isolated worktree on `codex/salar-background-jobs`.
- Preserve every unrelated dirty or untracked file in the main checkout.
- Start each task with its stated failing test and capture the RED result.
- Commit only after the task's focused tests pass.
- Push `codex/salar-background-jobs` after every green task so each checkpoint is recoverable without putting partial work on `main`.
- Merge and push `main` only after Task 9's complete verification and review gate.
- Do not deploy to Render or Hostinger as part of this plan; deployment is a separate production operation after the merged health check.

## File structure map

### Create

- `backend/app/services/jobs/__init__.py` — public job-engine exports.
- `backend/app/services/jobs/contracts.py` — statuses, handler protocol, result/error types, execution context.
- `backend/app/services/jobs/store.py` — enqueue, lease, heartbeat, progress/events, approval, retry, cancellation, terminal compare-and-set operations.
- `backend/app/services/jobs/registry.py` — stable job-kind to async-handler registry.
- `backend/app/services/jobs/worker.py` — single-process polling worker and per-job execution lifecycle.
- `backend/app/services/jobs/scheduler.py` — interval/cron next-run calculation and idempotent schedule enqueueing.
- `backend/app/services/jobs/workflow_handler.py` — first concrete handler for existing workflow actions.
- `backend/app/api/jobs.py` — authenticated job/event/approval/schedule endpoints.
- `backend/tests/test_job_store.py` — persistence, isolation, lease, idempotency, cancellation tests.
- `backend/tests/test_job_worker.py` — async execution, heartbeat, retries, recovery and cancellation tests.
- `backend/tests/test_job_scheduler.py` — interval/cron/timezone/idempotency tests.
- `backend/tests/test_jobs_api.py` — authentication, ownership, actions, serialization tests.
- `backend/tests/test_workflow_jobs.py` — legacy workflow-to-job compatibility tests.
- `frontend/src/components/JobsPanel.tsx` — queue/status/detail/approval UI.
- `frontend/src/jobs-contract.test.ts` — API contract and connected-shell integration tests.

### Modify

- `backend/app/models.py` — add `Job`, `JobEvent`, `JobApproval`, `JobSchedule`; link a job to its optional legacy `WorkflowRun` without altering the existing table.
- `backend/app/config.py` — add bounded worker/scheduler settings.
- `backend/app/main.py` — register router/handlers and start/stop worker safely in lifespan.
- `backend/app/api/workflows.py` — enqueue real jobs and return compatibility runs.
- `backend/app/services/agent.py` — route the manual workflow tool through the same enqueue path.
- `backend/pyproject.toml` — add a bounded cron parser dependency.
- `frontend/src/api.ts` — add typed job API contracts and methods.
- `frontend/src/main.tsx` — add a Jobs topbar control and panel to the authenticated shell.
- `frontend/src/styles.css` — responsive Jobs panel styling.

## Invariants to preserve throughout

- Every query or mutation is scoped by authenticated `owner_id`; optional `workspace_id` only narrows that boundary.
- A job id is never accepted as proof of ownership.
- `AgentRun` remains unchanged and continues to represent hidden specialist work.
- A synchronous SQLAlchemy `Session` is never kept alive across handler, network, sleep, or desktop awaits.
- Only the holder of the current lease token may heartbeat, request approval, retry, or write a terminal outcome.
- External errors are normalized to bounded codes and safe summaries before persistence or API exposure.
- A successful terminal state requires handler evidence; enqueueing or dispatch alone is not success.
- Cancellation is cooperative while a handler runs and compare-and-set fenced at completion.
- Retry attempts are bounded and scheduled with exponential backoff plus deterministic jitter.
- API responses never include lease tokens, raw exception traces, credentials, or full sensitive handler input.

## Task 1: Add the durable job ledger and atomic store

**Files:**

- Modify: `backend/app/models.py`
- Create: `backend/app/services/jobs/__init__.py`
- Create: `backend/app/services/jobs/contracts.py`
- Create: `backend/app/services/jobs/store.py`
- Create: `backend/tests/test_job_store.py`

- [ ] **Step 1: Write the failing model and enqueue tests**

Add tests that create two users and assert:

```python
def test_enqueue_is_idempotent_per_owner(session_factory):
    store = JobStore(session_factory)
    first = store.enqueue(owner_id="user-a", kind="test.echo", input_data={"value": 1}, idempotency_key="request-1")
    duplicate = store.enqueue(owner_id="user-a", kind="test.echo", input_data={"value": 2}, idempotency_key="request-1")
    other_owner = store.enqueue(owner_id="user-b", kind="test.echo", input_data={"value": 3}, idempotency_key="request-1")

    assert duplicate.id == first.id
    assert duplicate.input_data == {"value": 1}
    assert other_owner.id != first.id
```

Also cover scheduled jobs, ordered events, workspace filtering, JSON round trips, maximum attempts, and invalid status transitions.

- [ ] **Step 2: Run the focused test and record RED**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py -q
```

Expected: collection fails because `Job` and `JobStore` do not exist.

- [ ] **Step 3: Add the four additive tables**

Implement these fields and constraints in `backend/app/models.py`:

```python
class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_jobs_owner_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    workflow_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safe_error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    safe_error_detail: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    lease_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

Add `JobEvent(job_id, sequence, event_type, payload_json, created_at)` with a unique `(job_id, sequence)` constraint; `JobApproval(job_id, action_kind, preview_json, status, requested_at, expires_at, decided_at, decided_by)`; and `JobSchedule(owner_id, workspace_id, name, job_kind, input_json, schedule_type, schedule_value, timezone, next_run_at, enabled, last_enqueued_at, created_at, updated_at)`.

Keep `WorkflowRun` unchanged. The nullable unique `Job.workflow_run_id` points from the new table to the existing row, avoiding an `ALTER TABLE` on the deployed database while still providing a one-to-one compatibility projection.

- [ ] **Step 4: Define the stable contracts**

In `contracts.py`, define:

```python
TERMINAL_STATUSES = frozenset({"completed", "partial", "failed", "cancelled", "expired"})
CLAIMABLE_STATUSES = frozenset({"queued", "retrying"})

@dataclass(frozen=True)
class JobOutcome:
    status: Literal["completed", "partial"]
    result: dict[str, Any]

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
```

Define `JobSnapshot` as an immutable dataclass containing decoded input/result but never `lease_token`.

- [ ] **Step 5: Implement `JobStore` with fresh sessions and compare-and-set writes**

Required public methods:

```python
enqueue(*, owner_id, kind, input_data, idempotency_key, workspace_id=None,
        priority=100, scheduled_at=None, max_attempts=3) -> JobSnapshot
get_for_owner(*, owner_id, job_id) -> Optional[JobSnapshot]
list_for_owner(*, owner_id, workspace_id=None, statuses=None, limit=50, before=None) -> list[JobSnapshot]
list_events_for_owner(*, owner_id, job_id, after_sequence=0, limit=200) -> list[dict]
claim_next(*, worker_id, lease_seconds, now=None) -> Optional[ClaimedJob]
heartbeat(*, job_id, lease_token, lease_seconds, now=None) -> bool
record_progress(*, job_id, lease_token, progress, event_type, payload) -> bool
request_cancel(*, owner_id, job_id, now=None) -> JobSnapshot | None
is_cancel_requested(*, job_id, lease_token) -> bool
complete(*, job_id, lease_token, outcome, now=None) -> bool
fail_or_retry(*, job_id, lease_token, code, safe_detail, now=None) -> str
recover_abandoned(*, now=None) -> int
```

Use a separate `with session_factory() as db:` inside every method. Claim with one conditional update selecting the oldest due job ordered by `priority ASC, scheduled_at ASC, created_at ASC`; the update must require a claimable status and an absent/expired lease. Increment `attempt_count` on claim. Append each event in the same transaction as its state transition.

Generate event sequence as `coalesce(max(sequence), 0) + 1` while holding the transition transaction. Retry SQLite `IntegrityError` from competing event sequence insertion at most three times; never return a transition as successful if its event did not persist.

Normalize decoded JSON to dictionaries and reject non-object input at enqueue time. Clamp progress to `0.0..1.0` and enforce monotonic progress.

- [ ] **Step 6: Add contention, stale lease, cancellation, and isolation tests**

Use two independent SQLAlchemy sessions against the same SQLite file to verify:

- only one worker receives a job;
- an expired lease is recovered and claimed with a new token;
- the former lease token cannot heartbeat or complete;
- cancellation of queued work becomes terminal immediately;
- cancellation of running work sets a request and preserves the current lease;
- another owner cannot read, list, cancel, retry, approve, or inspect events;
- raw exception text is never stored by the public safe-error methods.

- [ ] **Step 7: Run focused GREEN checks**

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py -q
python -m compileall app
git diff --check
```

- [ ] **Step 8: Commit and push the checkpoint**

```powershell
git add backend/app/models.py backend/app/services/jobs backend/tests/test_job_store.py
git commit -m "feat(jobs): add durable job ledger"
git push -u origin codex/salar-background-jobs
```

## Task 2: Execute registered jobs with leases, heartbeat, retry, and cancellation

**Files:**

- Create: `backend/app/services/jobs/registry.py`
- Create: `backend/app/services/jobs/worker.py`
- Modify: `backend/app/services/jobs/contracts.py`
- Create: `backend/tests/test_job_worker.py`

- [ ] **Step 1: Write worker lifecycle tests before implementation**

Register deterministic handlers that complete, report progress, raise retryable/permanent errors, wait for cancellation, and exceed the original lease duration. Assert terminal status, attempt count, ordered events, and sanitized error fields.

Include this no-session-across-await probe: configure a SQLAlchemy `QueuePool` of size one, pause the handler on an `asyncio.Event`, and prove a separate store read completes before releasing the handler.

- [ ] **Step 2: Run RED**

```powershell
Set-Location backend
python -m pytest tests/test_job_worker.py -q
```

Expected: import failure for `JobRegistry` and `JobWorker`.

- [ ] **Step 3: Implement the handler registry and execution context**

The registry must reject duplicate kinds and expose no mutable handler map:

```python
JobHandler = Callable[[JobExecutionContext, dict[str, Any]], Awaitable[JobOutcome]]

class JobRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        if not kind or kind in self._handlers:
            raise ValueError("Job kind must be non-empty and unique")
        self._handlers[kind] = handler

    def resolve(self, kind: str) -> Optional[JobHandler]:
        return self._handlers.get(kind)
```

`JobExecutionContext` exposes `job_id`, `owner_id`, `workspace_id`, and async methods `progress`, `raise_if_cancelled`, `request_approval`, and `fence_external_action`. Each method calls a short-session store operation and verifies the current lease token internally. `fence_external_action` performs an immediate token-scoped lease renewal directly before a handler dispatches an irreversible external request.

- [ ] **Step 4: Implement `JobWorker.run_once()` and its managed loop**

Execution sequence:

1. recover abandoned claims;
2. claim one due job;
3. resolve handler or terminally fail with `unknown_job_kind`;
4. start a heartbeat task;
5. await the handler without any open DB session;
6. stop and await heartbeat;
7. check cancellation and lease ownership;
8. compare-and-set terminal outcome or retry;
9. log only job id, kind, and safe code.

Heartbeat interval must be less than one third of the lease duration. If heartbeat loses ownership, cancel the local handler task and do not write a terminal state.

Retry delay formula:

```python
base = min(retry_max_seconds, retry_base_seconds * (2 ** max(0, attempt_count - 1)))
jitter = int(hashlib.sha256(job_id.encode()).hexdigest()[:4], 16) % max(1, base // 5)
scheduled_at = now + timedelta(seconds=base + jitter)
```

Cancellation propagates as `JobCancelled`, not `failed`. Unexpected exceptions are logged server-side with traceback but persisted as `job_execution_failed` and `The job could not be completed.`

- [ ] **Step 5: Test restart recovery and token fencing**

Verify a worker stopped after claim leaves a running job that becomes retryable after lease expiry; the new worker completes it; the old worker's late result is rejected. Verify retry exhaustion ends in `failed`, not an infinite loop.

- [ ] **Step 6: Run focused GREEN checks**

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py tests/test_job_worker.py -q
python -m compileall app
git diff --check
```

- [ ] **Step 7: Commit and push**

```powershell
git add backend/app/services/jobs backend/tests/test_job_worker.py
git commit -m "feat(jobs): execute leased background work"
git push origin codex/salar-background-jobs
```

## Task 3: Add guarded job approvals

**Files:**

- Modify: `backend/app/services/jobs/store.py`
- Modify: `backend/app/services/jobs/contracts.py`
- Modify: `backend/app/services/jobs/worker.py`
- Modify: `backend/tests/test_job_store.py`
- Modify: `backend/tests/test_job_worker.py`

- [ ] **Step 1: Add failing approval tests**

Cover request, approve, reject, expiry, duplicate decisions, wrong-owner decisions, cancellation while waiting, and worker resume. Assert previews are JSON objects and do not contain configured secret keys.

- [ ] **Step 2: Run RED**

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py tests/test_job_worker.py -k approval -q
```

- [ ] **Step 3: Implement approval pause/resume**

Add store methods:

```python
request_approval(*, job_id, lease_token, action_kind, preview, expires_at) -> str
decide_approval(*, owner_id, approval_id, decision, decided_by, now=None) -> JobSnapshot | None
get_approval_decision(*, job_id, approval_id) -> Literal["approved", "rejected", "expired", "pending"]
```

`request_approval` atomically inserts the approval, changes job status to `waiting_approval`, clears the lease, and records `approval.requested`. Approval changes the job to `queued`; rejection changes it to `cancelled`; expiry changes it to `expired`. Each transition is conditional on `pending` so two decisions cannot both win.

The handler receives the approval identifier in a structured pause outcome. On the next claim it receives approved decisions in its input execution metadata and must revalidate policy immediately before any external action.

- [ ] **Step 4: Add adversarial decision tests**

Use two sessions to decide the same approval concurrently. Assert one conditional update succeeds, one returns the already-decided snapshot, only one decision event is present, and the job has one terminal/resumable state.

- [ ] **Step 5: Run GREEN and push**

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py tests/test_job_worker.py -q
python -m compileall app
git diff --check
git add backend/app/services/jobs backend/tests/test_job_store.py backend/tests/test_job_worker.py
git commit -m "feat(jobs): pause consequential work for approval"
git push origin codex/salar-background-jobs
```

## Task 4: Add timezone-aware schedules

**Files:**

- Modify: `backend/pyproject.toml`
- Create: `backend/app/services/jobs/scheduler.py`
- Create: `backend/tests/test_job_scheduler.py`

- [ ] **Step 1: Add the cron dependency and failing schedule tests**

Add `"croniter>=2,<7"` to project dependencies. Tests must cover:

- interval values expressed as positive integer seconds;
- standard five-field cron expressions;
- IANA timezones through `zoneinfo.ZoneInfo`;
- daylight-saving transitions without double enqueue;
- invalid timezone/expression rejection;
- a disabled schedule;
- two schedulers racing on the same due row;
- idempotency key `schedule:{schedule_id}:{due_at_utc_iso}`.

- [ ] **Step 2: Run RED**

```powershell
Set-Location backend
python -m pytest tests/test_job_scheduler.py -q
```

- [ ] **Step 3: Implement pure next-run calculation**

```python
def calculate_next_run(*, schedule_type: str, schedule_value: str,
                       timezone_name: str, after_utc: datetime) -> datetime:
    """Return an aware UTC datetime strictly later than after_utc."""
```

Reject intervals below 10 seconds. For cron, convert `after_utc` into the selected timezone, ask `croniter` for the next local occurrence, require an aware result, then normalize to UTC. Bound the cron search to five years and convert parser exceptions to `InvalidSchedule` with a safe message.

- [ ] **Step 4: Implement scheduler compare-and-set enqueue**

`JobScheduler.enqueue_due(now)` reads a bounded page of due enabled schedules. For each row, compute `due_at`, enqueue through `JobStore` with the deterministic idempotency key, then update `last_enqueued_at` and `next_run_at` only when the stored `next_run_at` still equals the claimed due value. If another scheduler wins, the job uniqueness constraint returns the existing job and prevents duplication.

- [ ] **Step 5: Run GREEN and push**

```powershell
Set-Location backend
python -m pip install -e ".[test]"
python -m pytest tests/test_job_scheduler.py tests/test_job_store.py -q
python -m compileall app
git diff --check
git add backend/pyproject.toml backend/app/services/jobs/scheduler.py backend/tests/test_job_scheduler.py
git commit -m "feat(jobs): enqueue timezone-aware schedules"
git push origin codex/salar-background-jobs
```

## Task 5: Expose authenticated jobs, events, schedules, and approvals APIs

**Files:**

- Create: `backend/app/api/jobs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_jobs_api.py`

- [ ] **Step 1: Write failing authenticated API tests**

Cover:

```text
GET    /api/jobs
GET    /api/jobs/{job_id}
GET    /api/jobs/{job_id}/events
POST   /api/jobs/{job_id}/cancel
POST   /api/jobs/{job_id}/retry
POST   /api/job-approvals/{approval_id}/decision
GET    /api/job-schedules
POST   /api/job-schedules
PATCH  /api/job-schedules/{schedule_id}
DELETE /api/job-schedules/{schedule_id}
```

Assert 401 without auth, 404 for another owner's identifiers, 409 for illegal retry/decision transitions, 422 for invalid pagination/schedule payloads, and no lease token or raw input secret in serialized output.

- [ ] **Step 2: Run RED**

```powershell
Set-Location backend
python -m pytest tests/test_jobs_api.py -q
```

- [ ] **Step 3: Implement explicit request and response models**

Use Pydantic models inside `jobs.py`; do not accept untyped `dict` bodies for these endpoints. Limit list results to 100, events to 200, text fields to their database bounds, and JSON bodies to dictionaries. Serialize timestamps as ISO-8601 UTC strings.

Retry creates a new queued attempt only for `failed`, `partial`, `cancelled`, or `expired`, retaining the same job id and incrementing an explicit `manual_retry_count` event field. Completed jobs return 409. Cancellation is idempotent and returns the current state.

- [ ] **Step 4: Register the router and re-run tests**

Import and include `jobs_router` in `create_app`. Do not start the worker yet; API tests must remain deterministic.

- [ ] **Step 5: Run GREEN and push**

```powershell
Set-Location backend
python -m pytest tests/test_jobs_api.py tests/test_job_store.py tests/test_job_scheduler.py -q
python -m compileall app
git diff --check
git add backend/app/api/jobs.py backend/app/main.py backend/tests/test_jobs_api.py
git commit -m "feat(jobs): expose job control APIs"
git push origin codex/salar-background-jobs
```

## Task 6: Convert workflows from fake completion to durable jobs

**Files:**

- Create: `backend/app/services/jobs/workflow_handler.py`
- Modify: `backend/app/api/workflows.py`
- Modify: `backend/app/services/agent.py`
- Create: `backend/tests/test_workflow_jobs.py`

- [ ] **Step 1: Write failing compatibility and isolation tests**

Assert that manual test and event trigger endpoints create `WorkflowRun(status="running")` plus a queued `workflow.execute` job whose `workflow_run_id` references that run. Assert they do not claim success before the handler finishes. Explicitly prove `/api/workflows/trigger` only matches `Workflow.user_id == current_user.id`; the current endpoint lacks this owner filter.

Verify the `run_workflow` agent tool follows the same enqueue service and does not construct an immediate `completed` run.

- [ ] **Step 2: Run RED**

```powershell
Set-Location backend
python -m pytest tests/test_workflow_jobs.py -q
```

- [ ] **Step 3: Add one enqueue service shared by HTTP and agent tools**

In `workflow_handler.py`, implement the synchronous enqueue signature `enqueue_workflow_run(*, session_factory, owner_id: str, workflow_id: str, trigger_event: dict, idempotency_key: str) -> tuple[WorkflowRun, JobSnapshot]` and the async handler signature `execute_workflow(context: JobExecutionContext, input_data: dict[str, Any]) -> JobOutcome`.

The enqueue transaction verifies ownership, creates the compatibility `WorkflowRun`, enqueues a job, links `job_id`, increments workflow run metadata once, and commits atomically. If `JobStore.enqueue` cannot share that transaction, add `enqueue_in_session` as an internal store primitive and keep the public method as the short-session wrapper.

First-release supported actions are limited to the existing non-destructive workflow action schema. Unknown actions fail with `unsupported_workflow_action`; consequential actions request approval. Record per-action progress. Only after handler evidence is present should the linked run become `success`; partial/cancelled/failed jobs map to `error` with a safe result log.

- [ ] **Step 4: Replace both fake-success paths**

Update `test_workflow`, `process_trigger`, and the agent's `_run_workflow` helper to call `enqueue_workflow_run`. For event triggers, use the caller-provided event identifier when present; otherwise hash the canonical owner/type/data/workflow tuple so delivery retries return the same job.

- [ ] **Step 5: Run GREEN and push**

```powershell
Set-Location backend
python -m pytest tests/test_workflow_jobs.py tests/test_jobs_api.py tests/test_agent_orchestrator.py -q
python -m compileall app
git diff --check
git add backend/app/services/jobs/workflow_handler.py backend/app/api/workflows.py backend/app/services/agent.py backend/tests/test_workflow_jobs.py
git commit -m "fix(workflows): execute through durable jobs"
git push origin codex/salar-background-jobs
```

## Task 7: Manage worker and scheduler lifecycle in FastAPI

**Files:**

- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/jobs/worker.py`
- Modify: `backend/tests/test_job_worker.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Add failing lifespan tests**

Prove test environments do not start polling by default, enabled environments start exactly one managed task, shutdown cancels and awaits it, and a stopped app leaves no pending task or open session. Inject a fake clock/wait function instead of sleeping.

- [ ] **Step 2: Add bounded settings**

Add:

```python
jobs_worker_enabled: bool = True
jobs_poll_seconds: float = Field(default=1.0, ge=0.1, le=60)
jobs_lease_seconds: int = Field(default=30, ge=10, le=600)
jobs_heartbeat_seconds: int = Field(default=5, ge=1, le=200)
jobs_retry_base_seconds: int = Field(default=5, ge=1, le=3600)
jobs_retry_max_seconds: int = Field(default=300, ge=5, le=86400)
jobs_scheduler_seconds: float = Field(default=5.0, ge=0.5, le=300)
```

Validate heartbeat is less than one third of lease duration during worker construction. In the shared `client` fixture set `jobs_worker_enabled=False` to keep API tests deterministic.

- [ ] **Step 3: Start and stop one managed engine**

During lifespan startup, create registry/store/worker/scheduler, register `workflow.execute`, assign them to `app.state`, then call `asyncio.create_task(worker.run_forever(poll_seconds=active_settings.jobs_poll_seconds, scheduler=scheduler, scheduler_seconds=active_settings.jobs_scheduler_seconds), name="salar-job-worker")`. On shutdown call `worker.stop()`, cancel only if bounded graceful shutdown expires, await the task, then dispose the engine.

One loop may alternate schedule enqueueing and job execution; keep scheduler and worker classes independently callable so they can move into separate processes later.

- [ ] **Step 4: Run GREEN and push**

```powershell
Set-Location backend
python -m pytest tests/test_job_worker.py tests/test_job_scheduler.py tests/test_health.py -q
python -m compileall app
git diff --check
git add backend/app/config.py backend/app/main.py backend/app/services/jobs/worker.py backend/tests/test_job_worker.py backend/tests/conftest.py
git commit -m "feat(jobs): run managed background worker"
git push origin codex/salar-background-jobs
```

## Task 8: Add the responsive Jobs UI

**Files:**

- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/JobsPanel.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/jobs-contract.test.ts`

- [ ] **Step 1: Write the failing frontend contract tests**

Follow the repository's source-contract Vitest style. Assert typed methods call the exact endpoints, `main.tsx` mounts `JobsPanel` only for authenticated users, and the panel exposes status filters, progress, cancel/retry, approval preview, approve/reject, empty, loading, and safe-error states.

- [ ] **Step 2: Run RED**

```powershell
Set-Location frontend
npm test -- jobs-contract.test.ts
```

- [ ] **Step 3: Add typed API contracts**

Export `JobStatus`, `JobSummary`, `JobEvent`, `JobApproval`, and `JobSchedule` types. Add methods:

```typescript
jobs(params?: { statuses?: JobStatus[]; workspace_id?: string; limit?: number }): Promise<JobSummary[]>
job(id: string): Promise<JobSummary>
jobEvents(id: string, afterSequence?: number): Promise<JobEvent[]>
cancelJob(id: string): Promise<JobSummary>
retryJob(id: string): Promise<JobSummary>
decideJobApproval(id: string, decision: 'approved' | 'rejected'): Promise<JobSummary>
jobSchedules(): Promise<JobSchedule[]>
```

Build query strings with `URLSearchParams`; never interpolate user values outside encoding.

- [ ] **Step 4: Build `JobsPanel` as an accessible drawer**

The panel polls every five seconds only while open and pauses when `document.hidden`. It must abort stale requests on close/unmount, keep the last successful list during transient refresh failure, and display only safe server error details.

Required UI behavior:

- tabs: Active, Waiting, Completed;
- status label and semantic icon, not color alone;
- progress bar with `aria-valuenow`;
- job kind rendered as a human label;
- Cancel for queued/running/retrying/waiting states;
- Retry only for failed/cancelled/expired;
- approval preview in a bounded scroll region;
- explicit Approve and Reject buttons with pending state;
- desktop drawer and iPhone/PWA full-screen sheet with 44px minimum targets and safe-area padding.

- [ ] **Step 5: Integrate without changing the existing chat/live experience**

Add a Jobs button in `.topbar-actions` beside Live. Mount the panel as a sibling overlay inside the authenticated `App`; do not alter `Chat`, `Live`, Liquid Ether settings, authentication, pricing, or landing-page code.

- [ ] **Step 6: Run frontend GREEN checks and push**

```powershell
Set-Location frontend
npm test -- jobs-contract.test.ts
npm test
npm run build
git diff --check
git add frontend/src/api.ts frontend/src/components/JobsPanel.tsx frontend/src/main.tsx frontend/src/styles.css frontend/src/jobs-contract.test.ts
git commit -m "feat(web): add background jobs control center"
git push origin codex/salar-background-jobs
```

## Task 9: Complete integration, adversarial review, and merge gate

**Files:**

- Review all files changed by Tasks 1–8.
- Update tests only when a discovered behavior requires a regression test.

- [ ] **Step 1: Run the complete backend suite from a clean process**

```powershell
Set-Location backend
$env:SALAR_GEMINI_API_KEY='test-baseline-key'
python -m pytest -q
Remove-Item Env:SALAR_GEMINI_API_KEY
python -m compileall app
```

Expected: all tests pass with no worker task leaks. Existing dependency warnings may remain but must be reported accurately.

- [ ] **Step 2: Run complete frontend checks**

```powershell
Set-Location frontend
npm test
npm run build
```

Expected: all Vitest tests pass and Vite emits a production bundle.

- [ ] **Step 3: Run focused concurrency and ownership probes**

```powershell
Set-Location backend
python -m pytest tests/test_job_store.py tests/test_job_worker.py tests/test_job_scheduler.py tests/test_jobs_api.py tests/test_workflow_jobs.py -q
```

Manually inspect that:

- every store mutation filters by lease token or owner as appropriate;
- no `Session` variable crosses an `await`;
- no external send/action occurs after lease ownership is lost;
- expired schedules and approvals resolve once;
- API serializers omit tokens, raw exceptions, and sensitive input;
- workflow event triggers include the owner filter.

- [ ] **Step 4: Review scope and scan for incomplete implementation**

```powershell
Set-Location "C:\Users\JD\Documents\SALAR AI"
rg -n "TODO|FIXME|TBD|NotImplementedError|pass\s*(#.*)?$" backend/app/services/jobs backend/app/api/jobs.py frontend/src/components/JobsPanel.tsx
git diff --check
git status --short
git log --oneline origin/main..HEAD
```

Expected: no incomplete implementation markers, clean whitespace, only planned files changed, and one verified commit per task.

- [ ] **Step 5: Request final code review and fix all Critical/Important findings**

Review against `docs/superpowers/specs/2026-08-11-salar-capability-platform-design.md`, concentrating on session lifetimes, compare-and-set fencing, external-action ordering, cross-process safety, ownership, cancellation, and error sanitization. Add a failing regression test before each fix.

- [ ] **Step 6: Push the final feature checkpoint**

```powershell
git push origin codex/salar-background-jobs
```

- [ ] **Step 7: Merge only the verified feature into `main` and push**

From the main checkout, first verify unrelated user changes are untouched. Then:

```powershell
git switch main
git pull --ff-only origin main
git merge --no-ff codex/salar-background-jobs -m "merge: durable background jobs"
git push origin main
```

If `main` moved or any conflict overlaps user changes, stop before merging and report the exact conflict. Never reset, clean, stash, or overwrite the user's dirty files.

## Completion evidence

Record in the final handoff:

- feature and merge commit hashes;
- pushed branch and `main` confirmation;
- exact backend/frontend pass counts;
- worker disabled/enabled behavior verified in tests;
- no-session-across-await and stale-lease fencing evidence;
- workflow fake-success paths removed;
- any pre-existing warnings or deferred production deployment work.
