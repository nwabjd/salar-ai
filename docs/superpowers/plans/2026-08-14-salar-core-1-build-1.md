# SALAAR CORE 1.0 — Build 1 Implementation Plan

**Date:** 2026-08-14
**Spec:** `docs/superpowers/specs/2026-08-14-salar-core-1-build-1-design.md`
**Goal:** Deliver the vertical slice — one request through Brain → Agents → Tools → Verify → Self-Correct → Confirmed, fully traced.

## Conventions

- Tests: pytest. Run from `backend/`: `python -m pytest -q`. Full suite must stay green after every task.
- New modules live in `backend/app/services/core/`. Keep them self-contained; no circular imports with `services/agent.py` — import `execute_tool` lazily inside functions when needed.
- `app.state` is the wiring surface (see `app/main.py` lifespan).
- TDD: write the test for each unit first (red), then the implementation (green).

## File map

```
backend/app/services/core/
├── __init__.py          # exports
├── events.py            # CoreBus, EVENT_* constants, CoreEvent, CoreEventLog model usage
├── traces.py            # CoreTraceStore helpers (create/complete/step)
├── toolspec.py          # ToolSpec, ToolRegistry
├── verification.py      # VerificationEngine, VerifierResult
├── confidence.py        # ConfidenceSystem
├── correction.py        # SelfCorrectionLoop
├── brain.py             # Intent, CorePlan, PlanStep, CoreBrain
├── runtime.py           # AgentRuntime (reuses AgentRun/AgentRunStep)
├── supervisor.py        # Supervisor
└── pipeline.py          # CorePipeline, CoreRunResult

backend/app/api/core.py            # REST routes
backend/app/models.py              # + CoreTask, CoreTrace, CoreTraceStep, CoreEventLog
backend/app/main.py                # lifespan wiring (additive only)

backend/tests/test_core_bus.py
backend/tests/test_core_toolspec.py
backend/tests/test_core_verification.py
backend/tests/test_core_confidence.py
backend/tests/test_core_correction.py
backend/tests/test_core_supervisor.py
backend/tests/test_core_pipeline.py
backend/tests/test_core_api.py
```

## Task 0 — Baseline

Run `python -m pytest -q` in `backend/`. Record the pass count. Any failure before we start is pre-existing; report it.

## Task 1 — Models (`models.py`)

Add four tables following the existing style (SQLAlchemy 2.0 `Mapped`/`mapped_column`, `token_id`, `utcnow`):

- `CoreTask`: `id, user_id (FK users), request (Text), goal (Text, default ""), intent_kind (str), status (str, default "queued"), confidence (Float, default 0.0), trace_id (str, nullable), created_at, updated_at`.
- `CoreTrace`: `id, task_id (FK core_tasks), status (str, default "running"), steps_count (int, default 0), started_at, finished_at (nullable)`.
- `CoreTraceStep`: `id, trace_id (FK core_traces), stage (str), detail_json (Text, default "{}"), started_at, finished_at (nullable), duration_ms (int, nullable)`.
- `CoreEventLog`: `id, trace_id (str, nullable, index), event_type (str), payload (Text, default "{}"), created_at`.

Test: `tests/test_core_models.py` (create, commit, reload; FK cascade). Existing suite green.

## Task 2 — EventBus (`events.py`)

- `EVENT_*` constants: `TASK_STARTED, TASK_PLANNED, AGENT_SPAWNED, AGENT_STEP, AGENT_FINISHED, TOOL_CALLED, TOOL_RESULT, VERIFICATION_PASSED, VERIFICATION_FAILED, CORRECTION_ATTEMPT, TASK_COMPLETED, TASK_FAILED, SUPERVISOR_ALERT`.
- `CoreEvent` (pydantic): `type, payload (dict), trace_id (optional str), created_at (datetime, default now)`.
- `CoreBus`:
  - `__init__(self, db_factory)` — callable returning a fresh `Session`.
  - `subscribe(type, handler)` — in-memory registry.
  - `publish(event)` — async: journal to `CoreEventLog`, then dispatch to subscribers (each awaited, isolated by try/except logging errors).
  - `journal(event)` — async: persist to `CoreEventLog`.
  - `history(trace_id)` — list events for a trace (replay).

Test `test_core_bus.py`: publish dispatches to subscriber; handler error doesn't break other handlers; journal persisted; history replay in order.

## Task 3 — ToolSpec + ToolRegistry (`toolspec.py`)

- `ToolSpec` (frozen dataclass): `name, description, risk_level, permission_category, input_schema, output_schema, verification ("auto"|"none"|<verifier name>), undo (Optional[str]), cost_class`.
- `RISK_CATEGORY = {0:"read_only",1:"safe",2:"reversible",3:"sensitive",4:"destructive"}`.
- `ToolRegistry`:
  - `__init__(self, specs=None)`; ships specs for: `file_write, file_read, list_files, run_command, code_run, open_url, browse_page, search_knowledge, search_documents, send_message, notify, screenshot`.
  - `spec(name)` — explicit spec or default (`risk 2, reversible, verification "auto", cost "cheap"`).
  - `specs()` — list all.
  - `requires_approval(spec)` — `risk_level >= 3`.
  - `async run(name, args, user_id, db_session, is_admin=False)` — thin wrapper calling `execute_tool(name, args, user_id, db_session, is_admin)` from `services.agent` (lazy import).

Test `test_core_toolspec.py`: known spec fields, default fallback, requires_approval for a risk-4 spec, run() delegates to execute_tool for `list_files`.

## Task 4 — VerificationEngine (`verification.py`)

- `VerifierResult` (frozen): `passed (bool), confidence (float), evidence (str), verifier (str)`.
- `VerificationEngine`:
  - `__init__` registers built-ins.
  - `register(name, fn)` — `fn(spec, args, result, ctx) -> VerifierResult`.
  - `async verify(spec, args, result, ctx)` — dispatch by `spec.verification`.

Built-in verifiers:
- `file_write`: if result has a path, read it back; content equals intended → passed 0.99; else failed. (Use `ctx.temp_expected` or args content.)
- `file_read`: non-empty → 0.97.
- `list_files`: list/tuple/dict → 0.9.
- `run_command`: `exit_code == 0` → 0.95 else failed 0.2.
- `code_run`: no `"error"` key in result and output present → 0.93.
- `open_url`: result contains status 200–399 → 0.96.
- `notify`/`send_message`: `result.get("ok") is True` → 0.9.
- `auto` (default): non-null result and no exception → 0.8; else failed 0.5.
- `none`: passed, confidence 0.3, evidence "no verifier configured".

Test `test_core_verification.py`: each built-in passes on success-shaped results and fails on wrong-shaped ones.

## Task 5 — ConfidenceSystem (`confidence.py`)

- `combine(factors: Dict[str, float]) -> float`: weighted geometric mean (all weights 1.0 for now, override via `weights` arg).
- `escalate(score, threshold=0.7) -> bool`: `score < threshold`.

Test `test_core_confidence.py`: combine math (perfect→1.0, mixed→between), escalate boundary.

## Task 6 — SelfCorrectionLoop (`correction.py`)

- `StepOutcome` (dataclass): `step, status ("completed"|"failed"|"retrying"), attempts (list of dicts), verified (bool), confidence, result`.
- `SelfCorrectionLoop(MAX_ATTEMPTS=3, registry=None, verifier=None, confidence=None)`.
- `async execute(step, user_id, db_session) -> StepOutcome`:
  1. Loop up to `MAX_ATTEMPTS`: run the tool via registry, verify.
  2. Verified → return completed.
  3. Not verified → record attempt, `diagnose(step, attempt)` to produce a corrected `args`/`tool_name` (deterministic: fix `mkdir`→`mkdir -p`, append `--force`, strip and retry, etc.; fallback: same args), publish `CORRECTION_ATTEMPT`.
  4. Budget exhausted → status `failed`, full attempt history in `attempts`. **Never** return completed without a passed verifier.

Test `test_core_correction.py`:
- Deterministic success on first try.
- Deterministic failure→alternative: use `run_command` with `mkdir` where the target path exists as a file → verifier fails → correction tries `mkdir -p` → verified → completed (assert 2 attempts, corrected args).
- Budget exhaustion: a command that always fails → status failed, attempts length == MAX_ATTEMPTS, not completed.

## Task 7 — CoreBrain (`brain.py`)

- `Intent` (frozen dataclass): `goal, intent_kind, requires_approval (bool), can_parallelize (bool), confidence (float)`.
- `PlanStep` (frozen): `id, tool_name, args (dict), description, parallelizable (bool), needs_approval (bool)`.
- `CorePlan` (frozen): `steps (list[PlanStep]), agents (list[str]), model (str), requires_approval (bool), confidence (float)`.
- `CoreBrain`:
  - `resolve_intent(request) -> Intent` — **rules first** (deterministic, no model): keyword signals → `chat|research|action|plan|code|memory`. Ambiguous/conflict → optional LLM fallback via injected `classifier` callable (default None → deterministic only). Confidence from rule-match strength.
  - `plan(intent, user_id, db_session) -> CorePlan` — rules-based mapper for Build 1: `action` intent → a single PlanStep wrapping the dominant verb (mkdir/create/run); `code` → run_command/code_run steps; `research` → browse_page + search steps; default → single `send_message` step. Model chosen via `ModelRouter.capability_for`. `requires_approval` if any step tool risk ≥ 3.

Test `test_core_brain.py`: each intent kind resolved deterministically; plan shape valid; approval flag on risky steps.

## Task 8 — AgentRuntime (`runtime.py`)

- Reuses `AgentRun`/`AgentRunStep` from `models` + `AgentSwarm` decompose for agent selection.
- `async spawn(user_id, kind, task, trace_id) -> AgentRun` — create AgentRun, publish `AGENT_SPAWNED`.
- `async run(run_id, steps, ...)` — for each PlanStep: run through `SelfCorrectionLoop`, record `AgentRunStep` (name, status, attempt, detail_json, evidence_json), publish `AGENT_STEP`/`TOOL_CALLED`/`TOOL_RESULT`/`VERIFICATION_*` events. Agents receive prior agents' results via the bus (`AGENT_FINISHED` events read from `history(trace_id)`).
- `async retire(run_id)` — mark completed/failed, publish `AGENT_FINISHED`.
- `live_agents()` — AgentRun rows with status `running`.

Test `test_core_runtime.py`: spawn→run (fake steps)→retire lifecycle; `live_agents` empty after retire; step rows persisted with evidence.

## Task 9 — Supervisor (`supervisor.py`)

- `Supervisor(bus)` with `watch(event) -> Optional[SupervisorAlert]` and `subscribe_to(bus)`.
- Rules:
  - Loop: ≥3 `TOOL_CALLED` with same `tool`+`args` in one trace → alert.
  - Failure cascade: ≥2 `VERIFICATION_FAILED` on same trace → alert.
  - Conflict: ≥2 `AGENT_FINISHED` in a trace with results where `content_dissimilarity > 0.7` (simple overlap ratio) and confidence < 0.7 → alert.
  - Token spike: average payload length of last 3 `TOOL_RESULT` > 50 KB → alert.
  - Dangerous action: `TOOL_CALLED` with `risk_level >= 3` and no `approval` event in trace → alert (publish `SUPERVISOR_ALERT`).
- Alerts are dataclasses: `rule, trace_id, message, severity`.

Test `test_core_supervisor.py`: each rule fires on a synthetic event stream; no alert on clean stream.

## Task 10 — CorePipeline (`pipeline.py`)

- `CoreRunResult` (dataclass): `requested, attempted (list[str]), verified (list[str]), status, confidence, trace_id, events (list[str])`.
- `CorePipeline(brain, runtime, bus, supervisor, db_factory)`:
  - `async run(request, user_id, db_session) -> CoreRunResult`:
    1. Create `CoreTask` + `CoreTrace`; publish `TASK_STARTED`.
    2. `brain.resolve_intent` + `brain.plan`; publish `TASK_PLANNED`.
    3. `plan.requires_approval` → status `awaiting_approval`, return (no execution).
    4. `runtime.spawn` → `runtime.run` (supervisor watching each event) → `runtime.retire`.
    5. Aggregate verified results; final confidence = combine of step confidences.
    6. Status `completed` if all steps verified else `failed`; publish `TASK_COMPLETED`/`TASK_FAILED`.
    7. Update CoreTask/CoreTrace (steps_count, finished_at, duration via trace steps).
  - `async approve(task_id, approve: bool, db_session)` — resume awaiting-approval task (approve → re-run, deny → status `denied`).

Test `test_core_pipeline.py`:
- Happy path: `POST`-level unit call with a `file_write` style step (monkeypatched tool that writes a temp file) → `status=completed`, `verified` non-empty, confidence ≥ 0.7, trace has ≥ 5 steps.
- Approval path: risky step → `awaiting_approval`, no tools executed.
- Correction path: first attempt fails → completed after retry (via a registry whose verifier fails once).
- Failure path: always-failing step → status `failed`, honest `attempted` list.

## Task 11 — API (`api/core.py`)

Routes (auth via existing `get_current_user` dependency):
- `POST /api/core/run` body `{request, goal?}` → `CoreRunResult` or `{status:"awaiting_approval"}`.
- `POST /api/core/run/{task_id}/approve` body `{approve: bool}`.
- `GET /api/core/traces/{trace_id}` → trace + steps.
- `GET /api/core/traces` → recent traces (limit).
- `GET /api/core/status` → `{live_agents, alerts, bus_events_count}`.

Test `test_core_api.py`: happy-path 200 + contract fields; approval 200; traces endpoints 200; status 200.

## Task 12 — Wiring (`main.py` lifespan)

In the existing lifespan (additive), after existing services:
- Build `db_factory` from the existing session factory.
- `app.state.core_bus = CoreBus(db_factory)`.
- `app.state.verifier = VerificationEngine()`.
- `app.state.confidence = ConfidenceSystem()`.
- `app.state.core_registry = ToolRegistry()`.
- `app.state.correction = SelfCorrectionLoop(...)`.
- `app.state.core_brain = CoreBrain(...)`.
- `app.state.core_runtime = AgentRuntime(bus, ...)`.
- `app.state.supervisor = Supervisor(bus)`; `bus.subscribe` supervisor.
- `app.state.core_pipeline = CorePipeline(...)`.
- Register `api/core.py` router in the app creation.
- Shutdown: no new long-running tasks in Build 1 (bus is fire-and-forget), nothing to stop.

## Task 13 — Final verification

- Full suite: `python -m pytest -q` — all previous + new tests green.
- Live smoke via TestClient: `POST /api/core/run` with `{"request":"create folder test_dir_core"}` against a temp dir → assert `status=completed`, `verified` contains the path, confidence ≥ 0.7, trace retrievable.
- Commit with message following repo style (e.g. `feat(core): Build 1 — autonomous intelligence runtime vertical slice`).
