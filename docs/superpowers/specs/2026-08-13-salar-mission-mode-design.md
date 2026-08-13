# SALAR Mission Mode — Design

- **Date:** 2026-08-13
- **Status:** Approved (design review, 2026-08-13)
- **Scope:** Backend engine + REST API. No frontend changes in this iteration.

## 1. Overview

Mission Mode turns a high-level goal ("Organize my Downloads folder, find duplicate
files, back up important documents, and give me a report") into a durable, observable,
semi-autonomous execution: an LLM planner decomposes the goal into ordered tool steps,
a runner executes them with the existing agent tool set, dangerous actions stop for
user approval, and failures trigger bounded re-planning. Progress is recorded as an
append-only event timeline so a future Command Center / Mission Timeline UI can render
Goal → Plan → Tasks → Progress → Result.

### Goals
- Launch a mission from a natural-language goal via `POST /api/missions`.
- Plan the goal into ordered steps using only known tools.
- Execute steps autonomously, escalating dangerous actions to an approval queue.
- Re-plan (max 3×) when a step fails, then complete or fail with a report.
- Persist every step and timeline event so progress survives restarts.

### Non-goals (future iterations)
- Frontend Mission UI / Mission Timeline.
- Undo AI action / action replay.
- Multi-user collaboration on a mission.
- Model routing for missions; the planner/executor use the configured Gemini client.
- Chat auto-detection of missions ("launch a mission when the user says...").
- Approval persistence across restarts (waiting approvals become `interrupted` on boot).

## 2. Approach

Dedicated `services/missions/` package with an in-process asyncio `MissionRunner`,
one task per running mission. Missions are durable rows; the job engine's worker is
not used because missions are long-running, interactive (approval waits), and
LLM-driven — a poor fit for bounded-work-item handlers.

Reused foundations:
- Existing agent tools via `execute_tool(name, args, user_id, db, is_admin)` in `services/agent.py`.
- Tool schemas from `TOOL_DEFINITIONS` for the planner's prompt.
- Gemini client via `request.app.state.coordinator.gemini`.
- `token_id()` and existing model conventions in `models.py`.
- App-lifespan service pattern used by `IntelScheduler`/`JobWorker`.

## 3. Data model

New tables in `models.py`:

### `Mission`
| column | type | notes |
|---|---|---|
| `id` | String(32) PK | `token_id()` |
| `user_id` | FK users.id CASCADE, index | |
| `goal` | Text | user goal text |
| `mode` | String(16) | `"autonomous"` in v1 |
| `status` | String(24), index | `queued, planning, running, waiting_approval, completed, failed, cancelled, interrupted` |
| `plan_json` | Text | latest full plan snapshot (`[]` default) |
| `result_summary` | Text | final report text |
| `error` | Text | terminal error |
| `step_count` | Integer | total planned steps |
| `completed_count` | Integer | completed steps |
| `total_attempts` | Integer | tool calls made |
| `replan_count` | Integer | re-plans used |
| `created_at / updated_at / started_at / finished_at` | DateTime(timezone=True) | |

### `MissionStep`
| column | type | notes |
|---|---|---|
| `id` | String(32) PK | |
| `mission_id` | FK missions.id CASCADE, index | |
| `sequence` | Integer | per-mission ordering |
| `tool` | String(64) | tool name |
| `args_json` | Text | `"{}"` default |
| `danger_level` | String(16) | `safe`, `caution`, `dangerous` |
| `status` | String(24) | `pending, running, waiting_approval, approved, denied, completed, failed, cancelled` |
| `output_json` | Text | tool result |
| `error` | Text | step error |
| `approval_note` | Text | LLM rationale when requesting approval |
| `started_at / finished_at / created_at` | DateTime(timezone=True) | |

### `MissionEvent`
| column | type | notes |
|---|---|---|
| `id` | String(32) PK | |
| `mission_id` | FK missions.id CASCADE, index | |
| `sequence` | Integer | append-only ordering |
| `kind` | String(32) | `planned, step_started, step_completed, step_failed, approval_requested, approved, denied, replanned, message, completed, failed, cancelled, interrupted` |
| `detail_json` | Text | `"{}"` default |
| `created_at` | DateTime(timezone=True) | |

## 4. Planner

`services/missions/planner.py` — `MissionPlanner`.

- Input: `goal` + known tools (names + arg schemas from `TOOL_DEFINITIONS`).
- One LLM call producing a JSON plan: `{"steps": [{"tool": str, "args": dict, "rationale": str}]}`.
- Validated against a Pydantic schema (`MissionPlan`, `PlannedStep`).
- Malformed or invalid output → retry up to 3 attempts → raise `PlanningError`.
- **Re-plan mode:** same call, plus a progress snapshot (completed steps + outputs,
  failed step + error, remaining goal), returning only remaining steps.
- Limits: only known tools, max 50 steps, one tool per step, args must be objects.

## 5. Danger classification

`services/missions/safety.py` — deterministic, system-side (never LLM-decided).

Levels:
- `safe` — read-only: `list_*`, `read_*`, `search_*`, `get_*`, `calendar_*` reads, `browse_page`, `get_system_info`, etc.
- `caution` — writes, reversible/benign: `create_task`, `set_reminder`, `save_memory`, `file_write`, `write_file`, etc.
- `dangerous` — irreversible or external effect: deletes/overwrites, `run_command`, `email_send`, `device_command`, `power_control`, `code_run`, install/reboot, unknown tools.

Arg-sensitive rules (override base level):
- `run_command`: dangerous unless clearly read-only/benign (e.g., `dir`, `echo`).
- File tools: dangerous when args contain delete/overwrite targets.

API: `classify_tool(tool: str, args: dict) -> str` returning a level.

## 6. MissionRunner

`services/missions/runner.py` — `MissionRunner` (per-user single active mission).

- State: `_tasks: dict[mission_id -> asyncio.Task]`, `_approvals: dict[step_id -> asyncio.Event]`.
- `start()` / `stop()`: app lifespan. `start()` reconciles missions stuck in
  `planning/running/waiting_approval` → `interrupted` (+ events). Gated off when
  `settings.environment == "test"` (tests instantiate their own runner).
- `launch(user_id, goal, mode="autonomous")`:
  - Reject (409) if the user has an active mission (`queued/planning/running/waiting_approval`).
  - Create `Mission` (queued) + `queued` event; spawn mission task.
- `_run_mission(mission)`:
  1. status → `planning`; planner → plan; persist steps (pending), `plan_json`, `planned` event.
  2. status → `running`.
  3. For each pending step in order:
     - step → `running`, emit `step_started`.
     - If `dangerous`: step → `waiting_approval`, emit `approval_requested` with the
       LLM rationale as `approval_note`; await its asyncio.Event.
       - `approved` → step → `approved`, continue to execute.
       - `denied` → step → `denied`, emit `denied`, continue to next step.
     - Execute via `execute_tool(...)` with a **fresh DB session per step**, wrapped in
       `asyncio.to_thread` and `asyncio.wait_for` (10 min timeout). Increment
       `total_attempts`.
     - Success → step `completed`, store `output_json`, emit `step_completed`,
       increment `completed_count`.
     - Failure/timeout → step `failed`, emit `step_failed`. If `replan_count < 3`:
       increment, mark remaining pending steps `cancelled`, re-plan from current state,
       append new pending steps, emit `replanned`. Else mission → `failed` with error.
  4. All steps terminal → mission → `completed`; write best-effort result summary via a
     short LLM call (aggregated outputs; failure to summarize is non-fatal); emit `completed`.
- `approve(mission_id, step_id)` / `deny(mission_id, step_id, note="")`: ownership-checked
  by the API layer; persist status + event, set the asyncio.Event.
- `cancel(mission_id)`: cancel the task; mission → `cancelled`; pending + in-flight steps → `cancelled`.
- Concurrency: one active mission per user; no global cap otherwise.

## 7. API

`api/missions.py` (`APIRouter`, prefix `/api/missions`, auth `get_current_user`,
ownership checks on every mission/step lookup).

| method | path | body | notes |
|---|---|---|---|
| POST | `/api/missions` | `{goal, mode?}` | create + launch; 409 on active mission |
| GET | `/api/missions` | `limit`, `status?` | list |
| GET | `/api/missions/{id}` | — | mission + steps + recent events |
| GET | `/api/missions/{id}/events` | `since_sequence?` | incremental timeline |
| POST | `/api/missions/{id}/cancel` | — | |
| POST | `/api/missions/{id}/steps/{step_id}/approve` | — | |
| POST | `/api/missions/{id}/steps/{step_id}/deny` | `{note?}` | |

Serialization: mission dict (status, counters, current step), steps (tool, danger,
status, output, error, approval_note), events (kind, detail, created_at).

Wiring: register router in `main.py`; start/stop runner in lifespan (test env gated).

## 8. Error handling & edge cases

- Unknown tool in plan → step fails immediately → replan path.
- Malformed plan after 3 retries → mission `failed` with `PlanningError` message.
- Step timeout (10 min) → treated as step failure → replan.
- Cancel mid-step → mission `cancelled`; in-flight step `cancelled`; completed steps stay.
- All steps denied → mission still `completed`; summary notes denied actions.
- Restart mid-approval → mission `interrupted` (approvals do not persist in v1).
- Runner never holds a DB session across `await`s; fresh session per step.

## 9. Testing

Mirrors existing test style (`tmp_path` SQLite engines, `Base.metadata.create_all`,
injectable dependencies, no live network).

- `test_mission_safety.py`: tool-name + arg-sensitive classification; unknown → dangerous.
- `test_mission_planner.py`: mocked LLM → valid plan; invalid → retries; repeated invalid → `PlanningError`.
- `test_mission_runner.py`: injected fake `execute_tool`; happy path (safe/caution execute
  autonomously), dangerous → approval gate → approve continues, deny skips, failure → replan
  (bounded), replan cap → failed, cancel, 409 on concurrent launch.
- `test_mission_api.py`: launch/list/detail/events/approve/deny/cancel + ownership checks.
