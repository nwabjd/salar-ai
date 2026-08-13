# backend/app/services/missions/runner.py
import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ActionLog, Mission, MissionStep, token_id, utcnow
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
        from ..action_log import ActionLogger
        with self._sf() as db:
            mission = db.get(Mission, mission_id)
            before_state = {}
            undo_action = None
            is_undoable = False
            if tool in ("file_write", "write_file"):
                path = args.get("path")
                if path:
                    import os
                    if os.path.exists(path):
                        try:
                            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                                before_state = {"path": path, "content": fh.read()}
                            undo_action = {"tool": "file_write", "args": {"path": path, "content": before_state["content"]}}
                            is_undoable = True
                        except OSError:
                            pass
            logger = ActionLogger(db)
            from ..guardian import GuardianAnalyzer
            GuardianAnalyzer().flag_and_record(db, mission.user_id, tool, args, source="mission")
            action = logger.record(
                user_id=mission.user_id, source="mission", tool=tool,
                args=args, result={}, is_undoable=is_undoable,
                before_state=before_state, undo_action=undo_action,
            )
            db.commit()
            action_id = action.id

            result = await self._execute_tool(tool, args, mission.user_id, db, is_admin=False)

            with self._sf() as db:
                action = db.get(ActionLog, action_id)
                if action is not None:
                    action.result_json = json.dumps(result or {})
                    action.undo_status = "undoable" if (action.is_undoable and action.undo_action_json) else "none"
                    db.add(action)
                step = db.get(MissionStep, step_id)
                step.status = "completed"
                step.output_json = json.dumps(result)
                step.finished_at = utcnow()
                mission = db.get(Mission, mission_id)
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
