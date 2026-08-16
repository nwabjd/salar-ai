# backend/app/services/core/pipeline.py
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ...models import CoreTask, CoreTrace, CoreTraceStep, token_id, utcnow
from .brain import CoreBrain, CorePlan
from .confidence import ConfidenceSystem
from .events import (
    TASK_APPROVED,
    TASK_COMPLETED,
    TASK_DENIED,
    TASK_FAILED,
    TASK_PLANNED,
    TASK_STARTED,
    CoreBus,
    CoreEvent,
)
from .runtime import AgentRuntime
from .supervisor import Supervisor

log = logging.getLogger(__name__)


@dataclass
class CoreRunResult:
    requested: str
    attempted: List[str] = field(default_factory=list)
    verified: List[str] = field(default_factory=list)
    status: str = "queued"
    confidence: float = 0.0
    trace_id: str = ""
    events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested": self.requested,
            "attempted": self.attempted,
            "verified": self.verified,
            "status": self.status,
            "confidence": self.confidence,
            "trace_id": self.trace_id,
            "events": self.events,
        }


class CorePipeline:
    def __init__(
        self,
        brain: Optional[CoreBrain] = None,
        runtime: Optional[AgentRuntime] = None,
        bus: Optional[CoreBus] = None,
        supervisor: Optional[Supervisor] = None,
        db_factory: Optional[Callable[[], Any]] = None,
        confidence: Optional[ConfidenceSystem] = None,
    ) -> None:
        self.brain = brain or CoreBrain()
        self.runtime = runtime or AgentRuntime(bus=bus)
        self.bus = bus
        self.confidence = confidence or ConfidenceSystem()
        self.db_factory = db_factory
        self.supervisor = supervisor
        if supervisor is not None and bus is not None:
            supervisor.subscribe_to(bus)

    async def run(self, request: str, user_id: str, db_session=None) -> CoreRunResult:
        trace_id = token_id()
        task = CoreTask(id=token_id(), user_id=user_id, request=request, status="queued", trace_id=trace_id)
        trace = CoreTrace(id=trace_id, task_id=task.id, status="running")
        db_session.add_all([task, trace])
        db_session.commit()
        await self._publish(TASK_STARTED, {"task_id": task.id, "request": request}, trace_id)

        self._begin_step(db_session, trace_id, "intent")
        intent = self.brain.resolve_intent(request)
        self._end_step(db_session, trace_id, "intent", {"intent_kind": intent.intent_kind, "confidence": intent.confidence})

        task.intent_kind = intent.intent_kind
        task.goal = intent.goal

        self._begin_step(db_session, trace_id, "plan")
        plan = self.brain.plan(intent)
        self._end_step(db_session, trace_id, "plan", plan.to_dict())
        await self._publish(TASK_PLANNED, {"task_id": task.id, "plan": plan.to_dict()}, trace_id)

        if plan.requires_approval:
            task.status = "awaiting_approval"
            trace.status = "awaiting_approval"
            db_session.commit()
            return CoreRunResult(
                requested=request,
                status="awaiting_approval",
                trace_id=trace_id,
                events=[TASK_STARTED, TASK_PLANNED],
            )

        return await self._execute(task, trace, plan, user_id, db_session, trace_id)

    async def approve(self, task_id: str, approve: bool, db_session=None) -> CoreRunResult:
        task = db_session.get(CoreTask, task_id)
        if task is None or task.status != "awaiting_approval":
            raise ValueError(f"task {task_id} is not awaiting approval")
        trace = db_session.query(CoreTrace).filter(CoreTrace.task_id == task_id).first()

        if not approve:
            task.status = "denied"
            if trace is not None:
                trace.status = "denied"
            db_session.commit()
            await self._publish(TASK_DENIED, {"task_id": task_id}, task.trace_id)
            return CoreRunResult(requested=task.request, status="denied", trace_id=task.trace_id)

        task.status = "running"
        if trace is not None:
            trace.status = "running"
        db_session.commit()
        await self._publish(TASK_APPROVED, {"task_id": task_id}, task.trace_id)

        intent = self.brain.resolve_intent(task.request)
        self._begin_step(db_session, trace.id, "plan")
        plan = self.brain.plan(intent)
        self._end_step(db_session, trace.id, "plan", plan.to_dict())
        await self._publish(TASK_PLANNED, {"task_id": task_id, "plan": plan.to_dict()}, task.trace_id)

        return await self._execute(task, trace, plan, task.user_id, db_session, task.trace_id)

    async def _execute(self, task: CoreTask, trace: CoreTrace, plan: CorePlan, user_id: str, db_session, trace_id: str) -> CoreRunResult:
        self._begin_step(db_session, trace_id, "spawn")
        run = await self.runtime.spawn(user_id, "core", task.request, trace_id=trace_id, db_session=db_session)
        self._end_step(db_session, trace_id, "spawn", {"run_id": run.id})

        self._begin_step(db_session, trace_id, "execute")
        result = await self.runtime.run(run.id, plan.steps, user_id, db_session=db_session, trace_id=trace_id)
        self._end_step(db_session, trace_id, "execute", {"status": result["status"], "step_count": len(plan.steps)})

        self._begin_step(db_session, trace_id, "finalize")
        await self.runtime.retire(run.id, db_session=db_session, trace_id=trace_id)
        self._end_step(db_session, trace_id, "finalize", {"run_id": run.id, "status": result["status"]})

        status = result["status"]
        step_outcomes = result.get("outcomes", [])
        verified = [s.description for s, o in zip(plan.steps, step_outcomes) if o.verified]
        attempted = [s.description for s in plan.steps]
        final_confidence = result["confidence"]
        events = [e.type for e in self.bus.history(trace_id)] if self.bus is not None else []

        task.status = status
        task.confidence = final_confidence
        trace.status = status
        trace.finished_at = utcnow()
        trace.steps_count = db_session.query(CoreTraceStep).filter(CoreTraceStep.trace_id == trace_id).count()
        db_session.commit()

        await self._publish(
            TASK_COMPLETED if status == "completed" else TASK_FAILED,
            {"task_id": task.id, "status": status, "confidence": final_confidence, "verified": verified},
            trace_id,
        )
        events.append(TASK_COMPLETED if status == "completed" else TASK_FAILED)

        return CoreRunResult(
            requested=task.request,
            attempted=attempted,
            verified=verified,
            status=status,
            confidence=final_confidence,
            trace_id=trace_id,
            events=events,
        )

    async def _publish(self, event_type: str, payload: Dict[str, Any], trace_id: Optional[str]) -> None:
        if self.bus is not None:
            await self.bus.publish(CoreEvent(type=event_type, payload=payload, trace_id=trace_id))

    def _begin_step(self, db_session, trace_id: str, stage: str) -> None:
        db_session.add(CoreTraceStep(id=token_id(), trace_id=trace_id, stage=stage, started_at=utcnow()))
        db_session.commit()

    def _end_step(self, db_session, trace_id: str, stage: str, detail: Any) -> None:
        step = db_session.query(CoreTraceStep).filter(CoreTraceStep.trace_id == trace_id, CoreTraceStep.stage == stage).order_by(CoreTraceStep.started_at.desc()).first()
        if step is None:
            return
        started = step.started_at
        if started is not None and started.tzinfo is not None:
            started = started.replace(tzinfo=None)
        finished = utcnow().replace(tzinfo=None)
        step.finished_at = finished
        step.duration_ms = max(int((finished - started).total_seconds() * 1000), 0) if started is not None else 0
        step.detail_json = json.dumps(detail, default=str)
        db_session.commit()
