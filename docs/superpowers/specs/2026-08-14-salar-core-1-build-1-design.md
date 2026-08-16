# SALAAR CORE 1.0 — Autonomous Intelligence Runtime (Build 1: Vertical Slice)

**Date:** 2026-08-14
**Status:** Approved scope (Build 1 only)
**Author:** SALAR Engineering

## 1. Goal

Replace the current research-only orchestrator with a central intelligence runtime.
Build 1 delivers the **vertical slice**: the full execution loop working end-to-end
for a single request, fully traced and verified.

```
REQUEST → BRAIN (intent/plan/route) → AGENTS (spawn→act→report) → VERIFY → CONFIRM (confidence)
              ↑                                                        ↓
              └────────── SELF-CORRECTION (diagnose→retry→reverify) ←──┘
```

Every outcome distinguishes **requested** / **attempted** / **verified** and carries a
confidence score and trace id.

Build 1 is a **new, parallel execution path**. The existing chat path and its tests
remain untouched. Integration into the chat router is Build 2.

## 2. Principles

- **Verified, not attempted**: every tool outcome passes a verifier or is honestly marked unverified.
- **Traced, always**: one `trace_id` per request; every stage recorded with timing.
- **Confidence-gated autonomy**: decisions below threshold escalate (second model, approval, or verify).
- **Ephemeral agents**: spawned per task, retired when done.
- **Event-driven**: all subsystems communicate via the CoreBus, never direct calls.

## 3. New files (backend/app/services/core/)

```
backend/app/services/core/
├── __init__.py
├── events.py          # EventBus + event types + journaling
├── traces.py          # Trace model + step recording (observability)
├── toolspec.py        # ToolSpec + ToolRegistry (unified tool protocol)
├── verification.py    # VerificationEngine + per-tool verifiers
├── confidence.py      # ConfidenceSystem
├── correction.py      # SelfCorrectionLoop
├── brain.py           # CoreBrain (intent → plan → route)
├── runtime.py         # AgentRuntime (spawn/run/retire)
├── supervisor.py      # Supervisor (watchdog over the event stream)
└── pipeline.py        # CorePipeline (runs the whole loop for a Task)
```

Supporting additions:
- `backend/app/api/core.py` — REST routes: `POST /api/core/run`, `GET /api/core/traces/{id}`, `GET /api/core/traces`, `GET /api/core/status`.
- `backend/app/models.py` — `CoreTask`, `CoreTrace`, `CoreTraceStep` models.
- Tests: `backend/tests/test_core_pipeline.py`, `test_core_bus.py`, `test_core_verification.py`, `test_core_supervisor.py`.

## 4. Component specifications

### 4.1 EventBus (`events.py`)

Typed async pub/sub. Every published event is journaled to the DB (durable) and
dispatched to in-process subscribers.

```python
class CoreEvent(BaseModel):
    type: str
    payload: dict
    trace_id: Optional[str] = None
    created_at: datetime
```

```python
class CoreBus:
    def subscribe(self, event_type: str, handler: Callable) -> None
    async def publish(self, event: CoreEvent) -> None      # journal + dispatch
    async def journal(self, event: CoreEvent) -> None      # persist via JobEvent-like record
    def history(self, trace_id: str) -> List[CoreEvent]    # replay for audit/supervisor
```

Event types (Build 1): `TASK_STARTED`, `TASK_PLANNED`, `AGENT_SPAWNED`, `AGENT_STEP`,
`AGENT_FINISHED`, `TOOL_CALLED`, `TOOL_RESULT`, `VERIFICATION_PASSED`,
`VERIFICATION_FAILED`, `CORRECTION_ATTEMPT`, `TASK_COMPLETED`, `TASK_FAILED`,
`SUPERVISOR_ALERT`.

Journaling reuses the existing `JobEvent` persistence pattern (`services/jobs/`)
so the audit trail survives restarts.

### 4.2 Unified Tool Protocol (`toolspec.py`)

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_level: int            # 0 read-only, 1 safe, 2 reversible, 3 sensitive, 4 destructive
    permission_category: str   # "read_only" | "safe" | "reversible" | "sensitive" | "destructive"
    input_schema: dict
    output_schema: dict
    verification: str          # name of a registered verifier, or "auto"/"none"
    undo: Optional[str]        # name of an undo tool/strategy, or None
    cost_class: str            # "free" | "cheap" | "expensive"
```

`ToolRegistry` wraps the existing `execute_tool` dispatch. Build 1 ships `ToolSpec`s
for the core tool set: `file_write`, `file_read`, `list_files`, `run_command`,
`code_run`, `open_url`, `browse_page`, `search_knowledge`, `search_documents`,
`send_message`, `notify`, `screenshot`. Tools without an explicit spec fall back to
a default spec (risk 2, verification "auto").

The registry exposes `get_spec(name)`, `specs()`, `requires_approval(spec, user)`.

### 4.3 VerificationEngine (`verification.py`)

```python
@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    confidence: float          # 0.0–1.0 evidence strength
    evidence: str              # human-readable proof
    verifier: str

class VerificationEngine:
    def register(self, name, fn) -> None
    async def verify(self, spec, args, result, ctx) -> VerificationResult
```

Built-in verifiers (Build 1):
- `file_write` → read the file back; equal content = passed (0.99).
- `file_read` → non-empty content = passed (0.97).
- `list_files` → list matches expected shape = passed (0.9).
- `run_command` → `exit_code == 0` = passed (0.95); else failed.
- `code_run` → no exception and expected keys present = passed (0.93).
- `open_url` → HTTP status in 200–399 = passed (0.96).
- `notify`/`send_message` → result `ok` = passed (0.9).
- `auto` (default) → result is non-null and no error raised = passed (0.8), else failed (0.5).
- `none` → passed with confidence 0.3, evidence "no verifier configured".

### 4.4 ConfidenceSystem (`confidence.py`)

```python
class ConfidenceSystem:
    def combine(self, factors: Dict[str, float]) -> float   # weighted geometric mean
    def escalate(self, score: float, threshold: float = 0.7) -> bool
```

Decision factors (Build 1): verification confidence, model finish reason,
inter-agent agreement, tool stability history. Any decision scoring below `0.7`
escalates: retry with stronger model, request user approval, or add web verification.

### 4.5 SelfCorrectionLoop (`correction.py`)

```python
class SelfCorrectionLoop:
    MAX_ATTEMPTS = 3
    async def execute(self, plan_step, context) -> CorrectedResult
```

Per step: `attempt → inspect → diagnose → alternative → retry → verify`.
- Inspection: capture tool result + verification outcome.
- Diagnosis: `diagnose(step, attempts)` — LLM (flash) or deterministic error analysis
  produces a corrected instruction and alternative tool choice.
- Budget: max 3 attempts per step. On exhaustion, the step is marked failed with the
  full attempt history (never silently succeeds).
- Verification gates each retry: a retry only counts as done when the verifier passes.

### 4.6 CoreBrain (`brain.py`)

```python
@dataclass(frozen=True)
class Intent:
    goal: str
    intent_kind: str            # "chat" | "research" | "action" | "plan" | "code" | "memory"
    requires_approval: bool
    can_parallelize: bool
    confidence: float

@dataclass(frozen=True)
class CorePlan:
    steps: List[PlanStep]       # ordered; parallelizable steps marked
    agents: List[str]           # agent kinds to spawn
    model: str
    requires_approval: bool
    confidence: float

class CoreBrain:
    async def resolve_intent(self, request) -> Intent   # rules first, LLM fallback
    async def plan(self, intent, user, db) -> CorePlan   # one LLM call, structured JSON
    async def route(self, intent) -> RoutingDecision      # agent + model + tools
```

Intent resolution (Build 1): deterministic classifiers first (fast, zero model cost)
using existing regex signals; if no rule matches or signals conflict, an LLM call
(Gemini flash) classifies with a strict JSON schema. Both paths produce the same
`Intent` shape and a confidence score.

### 4.7 AgentRuntime (`runtime.py`)

```python
class AgentRuntime:
    async def spawn(self, agent_kind, task, trace_id) -> AgentRun
    async def run(self, run_id) -> AgentResult       # runs steps through the correction loop
    async def retire(self, run_id) -> None
    def live_agents(self) -> List[AgentRun]
```

Reuses `AgentRun`/`AgentRunStep` persistence from `services/swarm.py`. Agents
communicate by publishing `AGENT_FINISHED`/result events to the bus — the next agent
consumes them (agent-to-agent, not through the user).

### 4.8 Supervisor (`supervisor.py`)

```python
class Supervisor:
    async def watch(self, event: CoreEvent) -> Optional[SupervisorAlert]
```

Rules (Build 1):
- **Loop detection**: same tool + same args observed ≥ 3 times in one trace → alert.
- **Failure cascade**: ≥ 2 verification failures on the same step → alert + correction.
- **Conflicting agents**: two agents return contradictory outputs for the same task
  (confidence below 0.7 and content dissimilarity high) → alert.
- **Token spike**: estimated payload growth per step > threshold → alert.
- **Dangerous action**: tool spec risk_level ≥ 3 without a prior approval event → alert.

Supervisor alerts are published on the bus (`SUPERVISOR_ALERT`), recorded on the
trace, and surfaced via `GET /api/core/status`.

### 4.9 CorePipeline (`pipeline.py`)

The single entry that runs the loop for one request:

```python
class CorePipeline:
    async def run(self, request, user_id, db) -> CoreRunResult
```

Flow:
1. Create trace + publish `TASK_STARTED`.
2. `brain.resolve_intent` → `brain.plan` → publish `TASK_PLANNED`.
3. If `requires_approval` → return `awaiting_approval` state (no execution).
4. Spawn agents via runtime → each step through the correction loop + verification →
   publish `AGENT_*` and `TOOL_*`/`VERIFICATION_*` events.
5. Supervisor watches every event (raises alerts, may abort a runaway loop).
6. Compute final confidence → publish `TASK_COMPLETED`/`TASK_FAILED`.
7. Return `CoreRunResult{ requested, attempted, verified, status, confidence, trace_id }`.

## 5. Models

```python
class CoreTask(Base):        # a submitted request
    id, user_id, request, intent_kind, status, confidence, trace_id, created_at, updated_at

class CoreTrace(Base):       # one pipeline run
    id, task_id, status, steps_count, started_at, finished_at

class CoreTraceStep(Base):   # one observable stage
    id, trace_id, stage, detail_json, started_at, finished_at, duration_ms
```

`CoreRunResult` (API contract):

```json
{
  "requested": "create folder /tmp/hello",
  "attempted": "ran mkdir /tmp/hello",
  "verified": "folder /tmp/hello exists",
  "status": "completed",
  "confidence": 0.97,
  "trace_id": "trc_abc123",
  "events": ["TASK_STARTED", "TASK_PLANNED", "AGENT_SPAWNED", "TOOL_CALLED", "VERIFICATION_PASSED", "TASK_COMPLETED"]
}
```

## 6. API surface

- `POST /api/core/run` — `{ request, goal? }` → `CoreRunResult` (or `awaiting_approval`).
- `POST /api/core/run/{task_id}/approve` / `deny` — resolve an awaiting-approval task.
- `GET /api/core/traces/{trace_id}` — full trace with step timings.
- `GET /api/core/traces` — recent traces.
- `GET /api/core/status` — live agents, recent alerts, bus counters.

## 7. Wiring

- `main.py` lifespan instantiates: `CoreBus`, `VerificationEngine`, `ConfidenceSystem`,
  `CoreBrain`, `AgentRuntime`, `Supervisor`, `SelfCorrectionLoop`, `CorePipeline`.
  All placed on `app.state` (`app.state.core_bus`, `app.state.core_pipeline`, …).
- `CoreBus` subscribes the Supervisor at startup.
- The existing chat path is **not** modified in Build 1 (integration is Build 2).

## 8. Tests (Build 1)

- `test_core_bus.py` — publish/subscribe dispatch, journaling, trace replay.
- `test_core_toolspec.py` — registry defaults, approval checks, spec lookup.
- `test_core_verification.py` — each built-in verifier (file write read-back, command
  exit code, open_url HTTP check, generic auto/none).
- `test_core_confidence.py` — combine math, escalate threshold.
- `test_core_correction.py` — fails, verifies, retries with alternative, budget
  exhaustion, never silent success.
- `test_core_supervisor.py` — loop detection, failure cascade, dangerous action, conflict.
- `test_core_pipeline.py` — full happy path end-to-end; awaiting-approval path;
  correction path; failure path with honest reporting.
- `test_core_api.py` — REST routes contract.

All run with the existing pytest suite; existing tests must stay green.

## 9. Acceptance criteria (Build 1)

1. `POST /api/core/run` completes a file/create → verify → report cycle with
   `verified: "folder exists"` and confidence ≥ 0.9.
2. A deliberately failing step self-corrects (max 3 attempts) and either succeeds
   verified or fails with full attempt history — never silently succeeds.
3. Every run produces a full trace retrievable by `trace_id` with stage timings.
4. Supervisor catches a simulated infinite-loop agent and aborts it.
5. All existing tests remain green; new suite covers the vertical slice.
6. Agents are ephemeral: `live_agents` returns to empty after each run.
