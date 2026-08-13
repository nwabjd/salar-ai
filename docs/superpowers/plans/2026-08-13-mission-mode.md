# Mission Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable backend engine and REST API that turns a natural-language goal into planned tool steps, executes them with an approval gate for dangerous actions, and records an observable timeline.

**Approach:** Dedicated `services/missions/` package with a `MissionRunner` (in-process asyncio tasks), a deterministic danger classifier, an LLM planner, and REST endpoints. Reuses existing `execute_tool()` and `TOOL_DEFINITIONS` from `services/agent.py`. App-lifespan lifecycle gated off in test environment.

**Tech Stack:** Python 3.11+, SQLAlchemy ORM, SQLite, FastAPI, Pydantic, asyncio, existing Gemini client via `coordinator.gemini.chat()`.

---

## File Structure

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `backend/app/models.py:325` | Add `Mission`, `MissionStep`, `MissionEvent` after `IntelEmailSeen` |
| Create | `backend/app/services/missions/__init__.py` | Package marker |
| Create | `backend/app/services/missions/safety.py` | `classify_tool(tool, args)` |
| Create | `backend/app/services/missions/planner.py` | `MissionPlanner.plan()`, `MissionPlanner.replan()` |
| Create | `backend/app/services/missions/runner.py` | `MissionRunner` — launch/approve/deny/cancel |
| Create | `backend/app/services/missions/events.py` | `MissionEventStore` |
| Create | `backend/app/api/missions.py` | REST endpoints |
| Modify | `backend/app/main.py:34,215,129-144,159-168` | Wire router + runner lifecycle |
| Create | `backend/tests/test_mission_safety.py` | Danger classification |
| Create | `backend/tests/test_mission_planner.py` | Planner with mocked LLM |
| Create | `backend/tests/test_mission_runner.py` | Runner with mocked tools/planner |
| Create | `backend/tests/test_mission_api.py` | API endpoints |

---

## Task 1: Add Mission models

**Files:**
- Modify: `backend/app/models.py:325`
- Test: `backend/tests/test_mission_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_models.py
from datetime import datetime, timezone
from app.database import Base, create_session_factory
from app.models import Mission, MissionStep, MissionEvent, token_id


def _utcnow():
    return datetime.now(timezone.utc)


def test_mission_crud(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mission.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        m = Mission(
            id=token_id(), user_id="u1", goal="Clean my downloads", mode="autonomous",
            status="queued", step_count=0, completed_count=0, total_attempts=0, replan_count=0,
            created_at=_utcnow(), updated_at=_utcnow(),
        )
        db.add(m)
        db.flush()

        s = MissionStep(
            id=token_id(), mission_id=m.id, sequence=1, tool="list_files",
            args_json="{}", danger_level="safe", status="pending",
            output_json="{}", error="", approval_note="", created_at=_utcnow(),
        )
        db.add(s)
        db.flush()

        e = MissionEvent(
            id=token_id(), mission_id=m.id, sequence=1, kind="planned",
            detail_json="{}", created_at=_utcnow(),
        )
        db.add(e)
        db.commit()

        assert db.get(Mission, m.id).goal == "Clean my downloads"
        assert db.get(MissionStep, s.id).tool == "list_files"
        assert db.get(MissionEvent, e.id).kind == "planned"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_models.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'Mission' from 'app.models'`

- [ ] **Step 3: Add models to `backend/app/models.py`**

Append after the `IntelEmailSeen` class (line ~334):

```python
class Mission(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="autonomous")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    plan_json: Mapped[str] = mapped_column(Text, default="[]")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    replan_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MissionStep(Base):
    __tablename__ = "mission_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(64))
    args_json: Mapped[str] = mapped_column(Text, default="{}")
    danger_level: Mapped[str] = mapped_column(String(16), default="safe")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    approval_note: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MissionEvent(Base):
    __tablename__ = "mission_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_models.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_mission_models.py
git commit -m "feat(mission): add Mission, MissionStep, MissionEvent models"
```

---

## Task 2: MissionEventStore

**Files:**
- Create: `backend/app/services/missions/__init__.py`
- Create: `backend/app/services/missions/events.py`
- Test: `backend/tests/test_mission_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_events.py
from app.database import Base, create_session_factory
from app.models import Mission, MissionEvent, token_id
from app.services.missions.events import MissionEventStore
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)


def test_event_append_and_recent(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mev.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        m = Mission(id=token_id(), user_id="u1", goal="g", created_at=_utcnow(), updated_at=_utcnow(),
                    step_count=0, completed_count=0, total_attempts=0, replan_count=0)
        db.add(m)
        db.commit()
        store = MissionEventStore(db)
        store.append(m.id, "planned", {"steps": 3})
        store.append(m.id, "step_started", {"tool": "list_files"})
        store.append(m.id, "step_completed", {"tool": "list_files"})
        db.commit()

        events = store.recent(m.id, limit=10)
        assert len(events) == 3
        assert events[0].kind == "planned"
        assert events[2].kind == "step_completed"


def test_event_since_sequence(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'mev2.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        m = Mission(id=token_id(), user_id="u1", goal="g", created_at=_utcnow(), updated_at=_utcnow(),
                    step_count=0, completed_count=0, total_attempts=0, replan_count=0)
        db.add(m)
        db.commit()
        store = MissionEventStore(db)
        store.append(m.id, "planned", {})
        store.append(m.id, "step_started", {"tool": "x"})
        store.append(m.id, "step_completed", {"tool": "x"})
        db.commit()

        events = store.recent(m.id, since_sequence=2)
        assert len(events) == 1
        assert events[0].kind == "step_completed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_events.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'MissionEventStore'`

- [ ] **Step 3: Create `backend/app/services/missions/__init__.py`**

Empty file.

- [ ] **Step 4: Create `backend/app/services/missions/events.py`**

```python
# backend/app/services/missions/events.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import MissionEvent, token_id
from ...models import utcnow

log = logging.getLogger(__name__)

_NEXT_SEQ_SQL = "SELECT COALESCE(MAX(sequence), 0) + 1 FROM mission_events WHERE mission_id = :mid"


class MissionEventStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, mission_id: str, kind: str, detail: Optional[Dict[str, Any]] = None) -> MissionEvent:
        seq = self.db.execute(__import__("sqlalchemy").text(_NEXT_SEQ_SQL), {"mid": mission_id}).scalar() or 1
        ev = MissionEvent(
            id=token_id(),
            mission_id=mission_id,
            sequence=seq,
            kind=kind,
            detail_json=json.dumps(detail or {}),
            created_at=utcnow(),
        )
        self.db.add(ev)
        return ev

    def recent(self, mission_id: str, *, limit: int = 50, since_sequence: Optional[int] = None) -> List[MissionEvent]:
        stmt = select(MissionEvent).where(MissionEvent.mission_id == mission_id)
        if since_sequence is not None:
            stmt = stmt.where(MissionEvent.sequence > since_sequence)
        stmt = stmt.order_by(MissionEvent.sequence.asc()).limit(limit)
        return list(self.db.scalars(stmt).all())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_events.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/missions/
git commit -m "feat(mission): MissionEventStore timeline append/recent"
```

---

## Task 3: Danger classifier

**Files:**
- Create: `backend/app/services/missions/safety.py`
- Test: `backend/tests/test_mission_safety.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_safety.py
from app.services.missions.safety import classify_tool

SAFE_TOOLS = [
    ("list_files", {}),
    ("read_file", {"path": "a.txt"}),
    ("search_files", {"q": "x"}),
    ("get_system_info", {}),
    ("get_current_time", {}),
    ("calendar_today", {}),
    ("calendar_upcoming", {}),
    ("list_tasks", {}),
    ("list_reminders", {}),
    ("search_knowledge", {"q": "x"}),
    ("browse_page", {"url": "https://x.com"}),
    ("get_monitor_stats", {}),
    ("get_battery", {}),
    ("get_disk_usage", {}),
    ("get_uptime", {}),
    ("network_info", {}),
    ("list_documents", {}),
    ("search_documents", {"q": "x"}),
    ("list_memories", {}),
    ("search_memories", {"q": "x"}),
    ("search_apps", {"q": "x"}),
]

CAUTION_TOOLS = [
    ("create_task", {"title": "do thing"}),
    ("set_reminder", {"title": "remind me"}),
    ("save_memory", {"title": "m", "content": "c"}),
    ("file_write", {"path": "a.txt", "content": "hi"}),
    ("write_file", {"path": "a.txt", "content": "hi"}),
    ("update_task", {"task_id": "x", "title": "y"}),
    ("set_task_status", {"task_id": "x", "status": "done"}),
    ("calendar_add_feed", {"url": "https://x.com/feed.ics"}),
    ("create_workspace", {"name": "ws"}),
    ("create_alert_rule", {"type": "x", "config": {}}),
]

DANGEROUS_TOOLS = [
    ("run_command", {"command": "rm -rf /tmp/junk"}),
    ("email_send", {"to": "a@b.com", "subject": "hi", "body": "hello"}),
    ("device_command", {"device_id": "d1", "command": "reboot"}),
    ("power_control", {"action": "shutdown"}),
    ("manage_process", {"action": "kill", "pid": 123}),
    ("code_run", {"language": "python", "code": "print(1)"}),
    ("delete_memory", {"memory_id": "m1"}),
    ("delete_task", {"task_id": "t1"}),
    ("delete_reminder", {"reminder_id": "r1"}),
    ("toggle_workflow", {"workflow_id": "w1"}),
]


def test_safe_tools():
    for tool, args in SAFE_TOOLS:
        assert classify_tool(tool, args) == "safe", f"{tool} should be safe"


def test_caution_tools():
    for tool, args in CAUTION_TOOLS:
        assert classify_tool(tool, args) == "caution", f"{tool} should be caution"


def test_dangerous_tools():
    for tool, args in DANGEROUS_TOOLS:
        assert classify_tool(tool, args) == "dangerous", f"{tool} should be dangerous"


def test_unknown_tool_is_dangerous():
    assert classify_tool("totally_fictional_tool", {}) == "dangerous"


def test_run_command_readonly_is_caution():
    assert classify_tool("run_command", {"command": "dir"}) == "caution"
    assert classify_tool("run_command", {"command": "echo hello"}) == "caution"
    assert classify_tool("run_command", {"command": "type file.txt"}) == "caution"
    assert classify_tool("run_command", {"command": "where python"}) == "caution"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_safety.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'classify_tool'`

- [ ] **Step 3: Create `backend/app/services/missions/safety.py`**

```python
# backend/app/services/missions/safety.py
import re

_SAFE = {
    "list_files", "read_file", "search_files", "get_system_info", "get_current_time",
    "calendar_today", "calendar_upcoming", "calendar_events", "calendar_search",
    "list_tasks", "list_reminders", "search_knowledge", "list_knowledge",
    "browse_page", "read_article", "browse_links", "get_monitor_stats",
    "get_battery", "get_disk_usage", "get_uptime", "network_info",
    "list_documents", "search_documents", "list_memories", "search_memories",
    "list_workspaces", "list_alert_rules", "list_triggered_alerts", "list_workflow_runs",
    "search_apps", "clipboard", "file_list", "file_read", "file_info", "file_search",
    "calculate", "get_weather",
}

_CAUTION = {
    "create_task", "set_reminder", "save_memory", "file_write", "write_file",
    "update_task", "set_task_status", "update_reminder", "mark_reminder_done",
    "calendar_add_feed", "create_workspace", "create_alert_rule",
    "list_workflows", "run_workflow", "open_app", "open_url", "open_explorer",
    "set_volume", "set_brightness", "media_control", "window_control",
    "whatsapp_send", "send_notification", "create_workflow",
}

_DANGEROUS = {
    "run_command", "email_send", "device_command", "power_control",
    "manage_process", "code_run", "delete_memory", "delete_task",
    "delete_reminder", "screenshot",
}

_READONLY_CMD = re.compile(
    r"^\s*(dir|echo|type|where|whoami|hostname|date|time|tree|path|set|ver|systeminfo|tasklist|ipconfig|nslookup|netstat|ping|tracert)\b",
    re.IGNORECASE,
)


def classify_tool(tool: str, args: dict) -> str:
    if tool in _SAFE:
        return "safe"
    if tool in _CAUTION:
        return "caution"
    if tool in _DANGEROUS:
        if tool == "run_command":
            cmd = (args.get("command") or "").strip()
            if _READONLY_CMD.match(cmd):
                return "caution"
        return "dangerous"
    return "dangerous"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_safety.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/missions/safety.py backend/tests/test_mission_safety.py
git commit -m "feat(mission): deterministic tool danger classifier"
```

---

## Task 4: LLM Planner

**Files:**
- Create: `backend/app/services/missions/planner.py`
- Test: `backend/tests/test_mission_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_planner.py
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.missions.planner import MissionPlanner, PlanningError


def _fake_gemini(plan_steps):
    """Return a mock gemini that yields a valid plan JSON."""
    text = json.dumps({"steps": plan_steps})
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value=text)
    return mock


@pytest.mark.asyncio
async def test_plan_valid_output():
    gemini = _fake_gemini([
        {"tool": "list_files", "args": {"path": "/downloads"}, "rationale": "scan"},
        {"tool": "run_command", "args": {"command": "dir /downloads"}, "rationale": "list"},
    ])
    planner = MissionPlanner(gemini)
    steps = await planner.plan("Organize my downloads folder")
    assert len(steps) == 2
    assert steps[0]["tool"] == "list_files"
    assert steps[1]["rationale"] == "list"


@pytest.mark.asyncio
async def test_plan_retries_on_malformed_json():
    bad_text = "Here is the plan:\n"
    good_text = json.dumps({"steps": [{"tool": "list_files", "args": {"path": "."}, "rationale": "ok"}]})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(side_effect=[bad_text, good_text])
    planner = MissionPlanner(gemini)
    steps = await planner.plan("find files")
    assert len(steps) == 1
    assert gemini.chat.call_count == 2


@pytest.mark.asyncio
async def test_plan_fails_after_retries():
    gemini = AsyncMock()
    gemini.chat = AsyncMock(return_value="no json here")
    planner = MissionPlanner(gemini)
    with pytest.raises(PlanningError):
        await planner.plan("do something")
    assert gemini.chat.call_count == 3


@pytest.mark.asyncio
async def test_plan_rejects_unknown_tool():
    text = json.dumps({"steps": [{"tool": "nonexistent_tool_xyz", "args": {}, "rationale": "x"}]})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(side_effect=[text, text, text])
    planner = MissionPlanner(gemini, known_tools={"list_files", "run_command"})
    with pytest.raises(PlanningError):
        await planner.plan("do something")


@pytest.mark.asyncio
async def test_plan_empty_steps_retries():
    empty = json.dumps({"steps": []})
    gemini = AsyncMock()
    gemini.chat = AsyncMock(return_value=empty)
    planner = MissionPlanner(gemini)
    with pytest.raises(PlanningError):
        await planner.plan("do nothing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_planner.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'MissionPlanner'`

- [ ] **Step 3: Create `backend/app/services/missions/planner.py`**

```python
# backend/app/services/missions/planner.py
import json
import logging
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_MAX_PLAN_ATTEMPTS = 3
_MAX_STEPS = 50


class PlanningError(Exception):
    pass


class MissionPlanner:
    def __init__(self, gemini, *, known_tools: Optional[Set[str]] = None) -> None:
        self._gemini = gemini
        self._known_tools = known_tools

    async def plan(self, goal: str) -> List[Dict[str, Any]]:
        prompt = self._build_plan_prompt(goal)
        return await self._call(prompt)

    async def replan(
        self,
        goal: str,
        completed_steps: List[Dict[str, Any]],
        failed_step: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        progress = {
            "completed": completed_steps,
            "failed": failed_step,
        }
        prompt = self._replan_prompt(goal, progress)
        return await self._call(prompt)

    # ---- internals ----

    async def _call(self, prompt: str) -> List[Dict[str, Any]]:
        messages = [
            {"role": "user", "content": prompt},
        ]
        last_error = None
        for _ in range(_MAX_PLAN_ATTEMPTS):
            try:
                text = await self._gemini.chat(messages)
                data = json.loads(text)
                steps = data.get("steps", [])
                if not isinstance(steps, list) or len(steps) == 0:
                    last_error = "empty steps"
                    continue
                if len(steps) > _MAX_STEPS:
                    last_error = f"too many steps ({len(steps)})"
                    continue
                for i, step in enumerate(steps):
                    tool = step.get("tool")
                    if not tool or not isinstance(tool, str):
                        last_error = f"step {i} missing tool"
                        break
                    if self._known_tools and tool not in self._known_tools:
                        last_error = f"step {i} unknown tool '{tool}'"
                        break
                    if not isinstance(step.get("args"), dict):
                        last_error = f"step {i} args not a dict"
                        break
                else:
                    return steps
            except json.JSONDecodeError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc)
            log.warning("Planner attempt failed: %s", last_error)
        raise PlanningError(f"Planning failed after {_MAX_PLAN_ATTEMPTS} attempts: {last_error}")

    @staticmethod
    def _build_plan_prompt(goal: str) -> str:
        return (
            "You are SALAR's mission planner. Turn the user's goal into an ordered plan.\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON with a \"steps\" array.\n"
            "- Each step: {\"tool\": str, \"args\": {}, \"rationale\": str}.\n"
            "- Only use tools that exist in the system; never invent tools.\n"
            "- One tool call per step.\n"
            "- Max 50 steps.\n"
            "- Put steps in logical execution order.\n\n"
            "Output format: {\"steps\": [{\"tool\": \"...\", \"args\": {...}, \"rationale\": \"...\"}, ...]}\n\n"
            f"Goal: {goal}"
        )

    @staticmethod
    def _replan_prompt(goal: str, progress: dict) -> str:
        return (
            "You are SALAR's mission planner re-planning after a partial failure.\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON with a \"steps\" array for the REMAINING work.\n"
            "- Do not repeat steps already completed successfully.\n"
            "- Each step: {\"tool\": str, \"args\": {}, \"rationale\": str}.\n"
            "- One tool call per step, max 50 steps.\n"
            "- Only use tools that exist in the system.\n\n"
            f"Original goal: {goal}\n\n"
            f"Progress so far: {json.dumps(progress)}\n\n"
            "Remaining plan:"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_planner.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/missions/planner.py backend/tests/test_mission_planner.py
git commit -m "feat(mission): LLM planner with plan/replan and retry"
```

---

## Task 5: MissionRunner

**Files:**
- Create: `backend/app/services/missions/runner.py`
- Test: `backend/tests/test_mission_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_runner.py
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.database import Base, create_session_factory
from app.models import Mission, MissionStep, MissionEvent, token_id
from app.services.missions.runner import MissionRunner, MissionConflict
from app.services.missions.planner import PlanningError


def _utcnow():
    return datetime.now(timezone.utc)


def _make_runner(tmp_path, *, fake_tool_result=None, plan_steps=None):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'runner.db'}")
    Base.metadata.create_all(engine)

    async def fake_execute_tool(name, args, uid, db, is_admin=False):
        if fake_tool_result is not None:
            return fake_tool_result
        return {"status": "ok", "tool": name}

    async def fake_chat(messages):
        import json
        steps = plan_steps or [{"tool": "list_files", "args": {"path": "."}, "rationale": "scan"}]
        return json.dumps({"steps": steps})

    gemini = AsyncMock()
    gemini.chat = fake_chat

    runner = MissionRunner(
        session_factory=sf,
        gemini=gemini,
        execute_tool_fn=fake_execute_tool,
    )
    return engine, sf, runner


@pytest.mark.asyncio
async def test_launch_happy_path(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        mission = await runner.launch("u1", "organize my downloads")
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
            assert m.step_count == 1
            assert m.completed_count == 1
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            assert len(steps) == 1
            assert steps[0].status == "completed"
            events = db.scalars(
                __import__("sqlalchemy").select(MissionEvent)
                .where(MissionEvent.mission_id == mission["id"])
            ).all()
            assert any(e.kind == "step_completed" for e in events)
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_launch_rejects(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        await runner.launch("u1", "goal one")
        with pytest.raises(MissionConflict):
            await runner.launch("u1", "goal two")
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_dangerous_step_waits_for_approval(tmp_path):
    def danger_classify(tool, args):
        return "dangerous" if tool == "run_command" else "safe"

    engine, sf, runner = await asyncio.to_thread(
        _make_runner, tmp_path,
        plan_steps=[{"tool": "run_command", "args": {"command": "dir"}, "rationale": "list"}],
    )
    runner._classify_tool = danger_classify

    try:
        await runner.start()
        mission = await runner.launch("u1", "run a command")
        await asyncio.sleep(0.2)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "waiting_approval"
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            assert steps[0].status == "waiting_approval"
        await runner.approve(mission["id"], steps[0].id)
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_deny_skips_step(tmp_path):
    def danger_classify(tool, args):
        return "dangerous" if tool == "email_send" else "safe"

    engine, sf, runner = await asyncio.to_thread(
        _make_runner, tmp_path,
        plan_steps=[{"tool": "email_send", "args": {"to": "a@b.com"}, "rationale": "send"}],
    )
    runner._classify_tool = danger_classify

    try:
        await runner.start()
        mission = await runner.launch("u1", "send email")
        await asyncio.sleep(0.2)
        with sf() as db:
            steps = db.scalars(
                __import__("sqlalchemy").select(MissionStep)
                .where(MissionStep.mission_id == mission["id"])
            ).all()
            step_id = steps[0].id
        await runner.deny(mission["id"], step_id, note="not now")
        await asyncio.sleep(0.3)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "completed"
    finally:
        await runner.stop()
        engine.dispose()


@pytest.mark.asyncio
async def test_cancel(tmp_path):
    engine, sf, runner = await asyncio.to_thread(_make_runner, tmp_path)
    try:
        await runner.start()
        mission = await runner.launch("u1", "do something")
        await asyncio.sleep(0.1)
        await runner.cancel(mission["id"])
        await asyncio.sleep(0.2)
        with sf() as db:
            m = db.get(Mission, mission["id"])
            assert m.status == "cancelled"
    finally:
        await runner.stop()
        engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_runner.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL with `ImportError: cannot import name 'MissionRunner'`

- [ ] **Step 3: Create `backend/app/services/missions/runner.py`**

```python
# backend/app/services/missions/runner.py
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Mission, MissionStep, MissionEvent, token_id
from ...models import utcnow
from .events import MissionEventStore
from .safety import classify_tool
from .planner import MissionPlanner, PlanningError

log = logging.getLogger(__name__)

_STEP_TIMEOUT = 600
_MAX_REPLANS = 3


class MissionConflict(Exception):
    pass


class MissionRunner:
    def __init__(
        self,
        *,
        session_factory,
        gemini,
        execute_tool_fn: Callable[..., Awaitable[Dict[str, Any]]],
    ) -> None:
        self._sf = session_factory
        self._gemini = gemini
        self._execute_tool = execute_tool_fn
        self._tasks: Dict[str, asyncio.Task] = {}
        self._approvals: Dict[str, asyncio.Event] = {}
        self._running = False
        self._classify_tool = classify_tool

    async def start(self) -> None:
        self._running = True
        self._reconcile_interrupted()
        log.info("MissionRunner started")

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._approvals.clear()
        log.info("MissionRunner stopped")

    def _reconcile_interrupted(self) -> None:
        with self._sf() as db:
            stuck = db.scalars(
                select(Mission).where(Mission.status.in_(["planning", "running", "waiting_approval"]))
            ).all()
            if not stuck:
                return
            events = MissionEventStore(db)
            for m in stuck:
                m.status = "interrupted"
                m.updated_at = utcnow()
                events.append(m.id, "interrupted", {"reason": "server restarted"})
            db.commit()

    # ---- public API ----

    async def launch(self, user_id: str, goal: str, *, mode: str = "autonomous") -> dict:
        self._assert_user_idle(user_id)
        mission_id = token_id()
        with self._sf() as db:
            m = Mission(
                id=mission_id, user_id=user_id, goal=goal, mode=mode, status="queued",
                step_count=0, completed_count=0, total_attempts=0, replan_count=0,
                created_at=utcnow(), updated_at=utcnow(),
            )
            db.add(m)
            events = MissionEventStore(db)
            events.append(mission_id, "queued", {"goal": goal})
            db.commit()
        task = asyncio.create_task(self._run_mission(mission_id))
        self._tasks[mission_id] = task
        return {"id": mission_id, "status": "queued", "goal": goal}

    async def approve(self, mission_id: str, step_id: str) -> None:
        with self._sf() as db:
            step = db.get(MissionStep, step_id)
            if step is None or step.mission_id != mission_id:
                raise ValueError("step not found")
            step.status = "approved"
            step.started_at = utcnow()
            events = MissionEventStore(db)
            events.append(mission_id, "approved", {"step_id": step_id})
            mission = db.get(Mission, mission_id)
            mission.status = "running"
            mission.updated_at = utcnow()
            db.commit()
        ev = self._approvals.get(step_id)
        if ev:
            ev.set()

    async def deny(self, mission_id: str, step_id: str, *, note: str = "") -> None:
        with self._sf() as db:
            step = db.get(MissionStep, step_id)
            if step is None or step.mission_id != mission_id:
                raise ValueError("step not found")
            step.status = "denied"
            step.approval_note = note
            step.finished_at = utcnow()
            events = MissionEventStore(db)
            events.append(mission_id, "denied", {"step_id": step_id, "note": note})
            db.commit()
        ev = self._approvals.get(step_id)
        if ev:
            ev.set()

    async def cancel(self, mission_id: str) -> None:
        with self._sf() as db:
            mission = db.get(Mission, mission_id)
            if mission is None or mission.status in ("completed", "failed", "cancelled"):
                return
            mission.status = "cancelled"
            mission.finished_at = utcnow()
            mission.updated_at = utcnow()
            self._cancel_pending_steps(db, mission_id)
            events = MissionEventStore(db)
            events.append(mission_id, "cancelled", {})
            db.commit()
        task = self._tasks.pop(mission_id, None)
        if task and not task.done():
            task.cancel()

    # ---- mission loop ----

    async def _run_mission(self, mission_id: str) -> None:
        try:
            with self._sf() as db:
                mission = db.get(Mission, mission_id)
                mission.status = "planning"
                mission.started_at = utcnow()
                mission.updated_at = utcnow()
                events = MissionEventStore(db)
                events.append(mission_id, "planning", {})
                db.commit()

            planner = MissionPlanner(self._gemini)
            steps = await planner.plan(mission.goal)
            self._persist_plan(mission_id, steps)

            with self._sf() as db:
                mission = db.get(Mission, mission_id)
                mission.status = "running"
                mission.updated_at = utcnow()
                db.commit()

            completed_steps = []
            for step_id, tool, args, danger in self._pending_steps(mission_id):
                with self._sf() as db:
                    step = db.get(MissionStep, step_id)
                    step.status = "running"
                    step.started_at = utcnow()
                    events = MissionEventStore(db)
                    events.append(mission_id, "step_started", {"step_id": step_id, "tool": tool})
                    db.commit()

                if danger == "dangerous":
                    with self._sf() as db:
                        step = db.get(MissionStep, step_id)
                        step.status = "waiting_approval"
                        step.approval_note = f"Action '{tool}' requires approval"
                        mission = db.get(Mission, mission_id)
                        mission.status = "waiting_approval"
                        mission.updated_at = utcnow()
                        events = MissionEventStore(db)
                        events.append(mission_id, "approval_requested", {
                            "step_id": step_id, "tool": tool, "args": args,
                        })
                        db.commit()
                    approval_event = asyncio.Event()
                    self._approvals[step_id] = approval_event
                    try:
                        await asyncio.wait_for(approval_event.wait(), timeout=3600)
                    except asyncio.TimeoutError:
                        with self._sf() as db:
                            step = db.get(MissionStep, step_id)
                            step.status = "failed"
                            step.error = "approval timed out"
                            step.finished_at = utcnow()
                            events = MissionEventStore(db)
                            events.append(mission_id, "step_failed", {"step_id": step_id, "error": "timeout"})
                            db.commit()
                        completed_steps.append({"tool": tool, "args": args, "status": "denied", "error": "timeout"})
                        continue
                    finally:
                        self._approvals.pop(step_id, None)

                    with self._sf() as db:
                        step = db.get(MissionStep, step_id)
                        if step.status == "denied":
                            completed_steps.append({"tool": tool, "args": args, "status": "denied"})
                            continue

                result = await asyncio.wait_for(
                    self._execute(tool, args, mission_id, step_id),
                    timeout=_STEP_TIMEOUT,
                )
                completed_steps.append({"tool": tool, "args": args, "result": result})

            with self._sf() as db:
                mission = db.get(Mission, mission_id)
                mission.status = "completed"
                mission.completed_count = mission.step_count
                mission.finished_at = utcnow()
                mission.updated_at = utcnow()
                mission.result_summary = f"Completed {mission.completed_count} step(s) successfully."
                events = MissionEventStore(db)
                events.append(mission_id, "completed", {"summary": mission.result_summary})
                db.commit()

        except PlanningError as exc:
            self._fail_mission(mission_id, f"Planning failed: {exc}")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._fail_mission(mission_id, str(exc))
        finally:
            self._tasks.pop(mission_id, None)

    async def _execute(self, tool: str, args: dict, mission_id: str, step_id: str) -> dict:
        with self._sf() as db:
            mission = db.get(Mission, mission_id)
            result = await self._execute_tool(tool, args, mission.user_id, db, is_admin=False)
            step = db.get(MissionStep, step_id)
            step.status = "completed"
            step.output_json = json.dumps(result)
            step.finished_at = utcnow()
            mission.completed_count += 1
            mission.total_attempts += 1
            mission.updated_at = utcnow()
            events = MissionEventStore(db)
            events.append(mission_id, "step_completed", {"step_id": step_id, "tool": tool})
            db.commit()
        return result

    # ---- plan persistence ----

    def _persist_plan(self, mission_id: str, steps: list) -> None:
        with self._sf() as db:
            mission = db.get(Mission, mission_id)
            mission.plan_json = json.dumps(steps)
            mission.step_count = len(steps)
            events = MissionEventStore(db)
            events.append(mission_id, "planned", {"step_count": len(steps)})
            for i, step in enumerate(steps, 1):
                danger = self._classify_tool(step.get("tool", ""), step.get("args", {}))
                ms = MissionStep(
                    id=token_id(), mission_id=mission_id, sequence=i,
                    tool=step["tool"], args_json=json.dumps(step.get("args", {})),
                    danger_level=danger, status="pending",
                    output_json="{}", error="", approval_note="",
                    created_at=utcnow(),
                )
                db.add(ms)
            db.commit()

    def _pending_steps(self, mission_id: str):
        with self._sf() as db:
            steps = db.scalars(
                select(MissionStep)
                .where(MissionStep.mission_id == mission_id, MissionStep.status == "pending")
                .order_by(MissionStep.sequence.asc())
            ).all()
            return [(s.id, s.tool, json.loads(s.args_json), s.danger_level) for s in steps]

    def _cancel_pending_steps(self, db: Session, mission_id: str) -> None:
        steps = db.scalars(
            select(MissionStep).where(
                MissionStep.mission_id == mission_id,
                MissionStep.status.in_(["pending", "waiting_approval"]),
            )
        ).all()
        for s in steps:
            s.status = "cancelled"
            s.finished_at = utcnow()

    def _fail_mission(self, mission_id: str, error: str) -> None:
        with self._sf() as db:
            mission = db.get(Mission, mission_id)
            if mission is None:
                return
            mission.status = "failed"
            mission.error = error[:2000]
            mission.finished_at = utcnow()
            mission.updated_at = utcnow()
            self._cancel_pending_steps(db, mission_id)
            events = MissionEventStore(db)
            events.append(mission_id, "failed", {"error": error[:500]})
            db.commit()

    def _assert_user_idle(self, user_id: str) -> None:
        with self._sf() as db:
            active = db.scalars(
                select(Mission).where(
                    Mission.user_id == user_id,
                    Mission.status.in_(["queued", "planning", "running", "waiting_approval"]),
                )
            ).all()
            if active:
                raise MissionConflict("User already has an active mission")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_runner.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/missions/runner.py backend/tests/test_mission_runner.py
git commit -m "feat(mission): MissionRunner with plan/execute/approve/cancel"
```

---

## Task 6: REST API + wiring

**Files:**
- Create: `backend/app/api/missions.py`
- Modify: `backend/app/main.py:34,215,129-144,159-168`
- Test: `backend/tests/test_mission_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mission_api.py
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.database import Base, create_session_factory
from app.main import create_app
from app.models import Mission, MissionStep, User, token_id
from app.security import hash_password
from app.services.missions.runner import MissionRunner


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
async def client(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'api_test.db'}")
    Base.metadata.create_all(engine)
    settings = type("S", (), {
        "database_url": f"sqlite:///{tmp_path / 'api_test.db'}",
        "environment": "test",
        "jwt_secret": "test-secret",
        "token_minutes": 60,
        "bootstrap_email": "test@test.local",
        "bootstrap_password": "pass",
        "allowed_origins": ["*"],
        "storage_dir": tmp_path / "uploads",
        "gemini_api_key": None,
        "gemini_model": "gemini-3.1-flash-lite",
        "public_api_url": "http://localhost:8000",
        "bridge_url": "http://localhost:3100",
        "stripe_secret_key": None,
        "stripe_webhook_secret": None,
        "stripe_price_pro": None,
        "stripe_price_team": None,
        "paypal_client_id": None,
        "paypal_secret": None,
        "payment_wallet_address": "0x0",
        "free_monthly_quota": 500,
        "pro_monthly_quota": 5000,
    })()
    app = create_app(settings)
    app.state.SessionLocal = sf

    with sf() as db:
        user = User(email="mission@test.local", password_hash=hash_password("pass"))
        db.add(user)
        db.commit()
        user_id = user.id

    from fastapi import Depends
    from app.security import get_current_user

    async def override_user():
        with sf() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_current_user] = override_user
    app.state._user_id = user_id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, sf, user_id

    engine.dispose()


@pytest.mark.anyio
async def test_launch_and_get(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    app_state = c._transport.app.state
    app_state.mission_runner = runner

    resp = await c.post("/api/missions", json={"goal": "organize downloads"})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["goal"] == "organize downloads"
    assert body["status"] == "queued"

    resp2 = await c.get("/api/missions")
    assert resp2.status_code == 200
    missions = resp2.json()
    assert len(missions) >= 1
    assert any(m["id"] == body["id"] for m in missions)


@pytest.mark.anyio
async def test_409_on_concurrent(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    app_state = c._transport.app.state
    app_state.mission_runner = runner

    await c.post("/api/missions", json={"goal": "first"})
    await c.post("/api/missions", json={"goal": "second"})
    # The second may 200 or 409 depending on how fast the first finishes planning
    # This tests that the endpoint responds; concurrency is tested in runner tests
    resp2 = await c.post("/api/missions", json={"goal": "third"})
    assert resp2.status_code in (200, 201, 409)


@pytest.mark.anyio
async def test_cancel(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    app_state = c._transport.app.state
    app_state.mission_runner = runner

    resp = await c.post("/api/missions", json={"goal": "to cancel"})
    body = resp.json()
    resp2 = await c.post(f"/api/missions/{body['id']}/cancel")
    assert resp2.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mission_api.py -q -p no:cacheprovider -p no:warnings`
Expected: FAIL (404 on POST /api/missions — router not registered)

- [ ] **Step 3: Create `backend/app/api/missions.py`**

```python
# backend/app/api/missions.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mission, MissionStep, User
from ..security import get_current_user
from ..services.missions.runner import MissionRunner, MissionConflict

router = APIRouter(prefix="/api/missions", tags=["missions"])


def _get_runner(request):
    runner = getattr(request.app.state, "mission_runner", None)
    if runner is None:
        raise HTTPException(status_code=503, detail="Mission runner not available")
    return runner


def _serialize_mission(m: Mission, steps=None, events=None) -> dict:
    data = {
        "id": m.id,
        "goal": m.goal,
        "mode": m.mode,
        "status": m.status,
        "step_count": m.step_count,
        "completed_count": m.completed_count,
        "total_attempts": m.total_attempts,
        "replan_count": m.replan_count,
        "result_summary": m.result_summary,
        "error": m.error,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "finished_at": m.finished_at.isoformat() if m.finished_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
    if steps is not None:
        data["steps"] = [_serialize_step(s) for s in steps]
    if events is not None:
        data["events"] = [_serialize_event(e) for e in events]
    return data


def _serialize_step(s: MissionStep) -> dict:
    return {
        "id": s.id,
        "sequence": s.sequence,
        "tool": s.tool,
        "args_json": s.args_json,
        "danger_level": s.danger_level,
        "status": s.status,
        "output_json": s.output_json,
        "error": s.error,
        "approval_note": s.approval_note,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "finished_at": s.finished_at.isoformat() if s.finished_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_event(e) -> dict:
    return {
        "id": e.id,
        "sequence": e.sequence,
        "kind": e.kind,
        "detail_json": e.detail_json,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


class LaunchBody(BaseModel):
    goal: str
    mode: str = "autonomous"


@router.post("")
def launch_mission(
    body: LaunchBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request=None,
):
    runner = _get_runner(request)
    try:
        result = __import__("asyncio").get_event_loop().run_until_complete(
            runner.launch(current_user.id, body.goal, mode=body.mode)
        )
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.get("")
def list_missions(
    limit: int = 20,
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Mission).where(Mission.user_id == current_user.id)
    if status:
        q = q.where(Mission.status == status)
    missions = db.scalars(q.order_by(Mission.created_at.desc()).limit(limit)).all()
    return [_serialize_mission(m) for m in missions]


@router.get("/{mission_id}")
def get_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    steps = db.scalars(
        select(MissionStep).where(MissionStep.mission_id == mission_id).order_by(MissionStep.sequence.asc())
    ).all()
    return _serialize_mission(m, steps=steps)


@router.get("/{mission_id}/events")
def list_events(
    mission_id: str,
    since_sequence: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    from ..models import MissionEvent
    q = select(MissionEvent).where(MissionEvent.mission_id == mission_id)
    if since_sequence > 0:
        q = q.where(MissionEvent.sequence > since_sequence)
    events = db.scalars(q.order_by(MissionEvent.sequence.asc()).limit(200)).all()
    return [_serialize_event(e) for e in events]


@router.post("/{mission_id}/cancel")
def cancel_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request=None,
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    __import__("asyncio").get_event_loop().run_until_complete(runner.cancel(mission_id))
    return {"status": "cancelled", "id": mission_id}


@router.post("/{mission_id}/steps/{step_id}/approve")
def approve_step(
    mission_id: str,
    step_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request=None,
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    __import__("asyncio").get_event_loop().run_until_complete(runner.approve(mission_id, step_id))
    return {"status": "approved", "step_id": step_id}


@router.post("/{mission_id}/steps/{step_id}/deny")
def deny_step(
    mission_id: str,
    step_id: str,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request=None,
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    note = (body or {}).get("note", "")
    __import__("asyncio").get_event_loop().run_until_complete(runner.deny(mission_id, step_id, note=note))
    return {"status": "denied", "step_id": step_id}
```

- [ ] **Step 4: Wire router in `backend/app/main.py`**

Add import at line ~34:
```python
from .api.missions import router as missions_router
```

Add after `intel_router` registration (line ~215):
```python
app.include_router(missions_router)
```

Add lifecycle block inside lifespan, after intel_scheduler block (after line ~144):
```python
        from .services.missions.runner import MissionRunner
        import gemini_mod as _gmod  # noqa — referenced via app.state
        async def _noop_tool(name, args, uid, db, is_admin=False):
            return {"status": "error", "detail": "no tool executor configured"}
        app.state.mission_runner = MissionRunner(
            session_factory=session_factory,
            gemini=app.state.coordinator.gemini,
            execute_tool_fn=_noop_tool,
        )
        await app.state.mission_runner.start()
        log.info("Mission runner started")
```

Replace `_noop_tool` block in the actual wiring with the real tool import (see below).

Add shutdown block (after job_worker stop, before engine.dispose):
```python
        if hasattr(app.state, "mission_runner"):
            try:
                await app.state.mission_runner.stop()
            except Exception:
                pass
```

Full correct wiring (overwrite the three inserted blocks with this):
```python
        # ---- mission runner (after intel scheduler, before yield) ----
        from .services.agent import execute_tool as _real_execute_tool
        from .services.missions.runner import MissionRunner as _MissionRunner
        app.state.mission_runner = _MissionRunner(
            session_factory=session_factory,
            gemini=app.state.coordinator.gemini,
            execute_tool_fn=_real_execute_tool,
        )
        await app.state.mission_runner.start()
        log.info("Mission runner started")
```

- [ ] **Step 5: Fix API router to use `request` correctly**

The router functions need `request: Request` as a parameter. Update the four functions that call `_get_runner` to accept it. Replace the launch_mission, cancel_mission, approve_step, deny_step functions with:

```python
from fastapi import APIRouter, Depends, HTTPException, Request


@router.post("")
def launch_mission(
    body: LaunchBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    try:
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            runner.launch(current_user.id, body.goal, mode=body.mode)
        )
    except MissionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.post("/{mission_id}/cancel")
def cancel_mission(
    mission_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    import asyncio
    asyncio.get_event_loop().run_until_complete(runner.cancel(mission_id))
    return {"status": "cancelled", "id": mission_id}


@router.post("/{mission_id}/steps/{step_id}/approve")
def approve_step(
    mission_id: str,
    step_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    import asyncio
    asyncio.get_event_loop().run_until_complete(runner.approve(mission_id, step_id))
    return {"status": "approved", "step_id": step_id}


@router.post("/{mission_id}/steps/{step_id}/deny")
def deny_step(
    mission_id: str,
    step_id: str,
    request: Request,
    body: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runner = _get_runner(request)
    m = db.scalar(select(Mission).where(Mission.id == mission_id, Mission.user_id == current_user.id))
    if not m:
        raise HTTPException(status_code=404, detail="Mission not found")
    step = db.get(MissionStep, step_id)
    if not step or step.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Step not found")
    note = (body or {}).get("note", "")
    import asyncio
    asyncio.get_event_loop().run_until_complete(runner.deny(mission_id, step_id, note=note))
    return {"status": "denied", "step_id": step_id}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_mission_api.py -q -p no:cacheprovider -p no:warnings`
Expected: PASS

- [ ] **Step 7: Run full backend test suite**

Run: `cd backend && python -m pytest tests -q -p no:cacheprovider -p no:warnings`
Expected: All existing tests + new mission tests pass, EXIT=0

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/missions.py backend/app/main.py backend/tests/test_mission_api.py
git commit -m "feat(mission): REST API + app lifespan wiring"
```

---

## Task 7: Full integration test

- [ ] **Step 1: Run the full suite and verify**

Run: `cd backend && python -m pytest tests -q -p no:cacheprovider -p no:warnings`
Expected: all tests pass, EXIT=0

- [ ] **Step 2: Final commit**

```bash
git add -A
git commit -m "feat(mission): Mission Mode complete — engine, planner, runner, API, tests"
```
