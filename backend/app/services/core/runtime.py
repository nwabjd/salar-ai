# backend/app/services/core/runtime.py
import json
import logging
from typing import Any, Dict, List, Optional

from ...models import AgentRun, AgentRunStep, token_id
from .confidence import ConfidenceSystem
from .correction import SelfCorrectionLoop
from .events import (
    AGENT_FINISHED,
    AGENT_SPAWNED,
    AGENT_STEP,
    CoreBus,
    CoreEvent,
    TOOL_CALLED,
    TOOL_RESULT,
    VERIFICATION_FAILED,
    VERIFICATION_PASSED,
)

log = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(self, bus: Optional[CoreBus] = None, correction: Optional[SelfCorrectionLoop] = None, confidence: Optional[ConfidenceSystem] = None) -> None:
        self.bus = bus
        self.correction = correction or SelfCorrectionLoop()
        self.confidence = confidence or ConfidenceSystem()

    async def spawn(self, user_id: str, kind: str, task: str, trace_id: Optional[str] = None, db_session=None) -> AgentRun:
        run = AgentRun(id=token_id(), user_id=user_id, kind=kind, status="running", input_json=json.dumps({"task": task}))
        db_session.add(run)
        db_session.commit()
        if self.bus is not None:
            await self.bus.publish(CoreEvent(type=AGENT_SPAWNED, trace_id=trace_id, payload={"run_id": run.id, "kind": kind}))
        return run

    async def run(self, run_id: str, steps: List[Any], user_id: str, db_session=None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        prior_results = self._prior_agent_results(trace_id)
        step_outcomes = []
        all_verified = True
        sequence = 1

        for step in steps:
            if self.bus is not None:
                await self.bus.publish(
                    CoreEvent(type=TOOL_CALLED, trace_id=trace_id, payload={"tool": step.tool_name, "args": step.args, "description": step.description})
                )
            outcome = await self.correction.execute(step, user_id, db_session=db_session, trace_id=trace_id)
            if self.bus is not None:
                await self.bus.publish(
                    CoreEvent(type=TOOL_RESULT, trace_id=trace_id, payload={"tool": step.tool_name, "result": outcome.result, "status": outcome.status})
                )
                await self.bus.publish(
                    CoreEvent(
                        type=VERIFICATION_PASSED if outcome.verified else VERIFICATION_FAILED,
                        trace_id=trace_id,
                        payload={"step": step.id, "tool": step.tool_name, "confidence": outcome.confidence},
                    )
                )
            self._record_step(run_id, step, outcome, db_session, sequence)
            sequence += 1
            step_outcomes.append(outcome)
            if not outcome.verified:
                all_verified = False

        confidence = self.confidence.combine({f"step_{i}": o.confidence for i, o in enumerate(step_outcomes) if o.verified}) if step_outcomes else 0.0
        status = "completed" if all_verified else "failed"

        run = db_session.get(AgentRun, run_id)
        if run is not None:
            run.status = status
            run.output_json = json.dumps(
                {
                    "status": status,
                    "confidence": round(confidence, 4),
                    "steps": [{"id": o.step_id, "status": o.status, "verified": o.verified, "confidence": o.confidence, "attempts": len(o.attempts)} for o in step_outcomes],
                    "prior_results": prior_results,
                }
            )
            db_session.commit()

        if self.bus is not None:
            await self.bus.publish(
                CoreEvent(type=AGENT_STEP, trace_id=trace_id, payload={"run_id": run_id, "steps": [{"id": o.step_id, "status": o.status, "verified": o.verified} for o in step_outcomes]})
            )

        return {"status": status, "confidence": round(confidence, 4), "outcomes": step_outcomes, "prior_results": prior_results}

    async def retire(self, run_id: str, db_session=None, trace_id: Optional[str] = None) -> None:
        run = db_session.get(AgentRun, run_id)
        if run is None:
            return
        status = run.status if run.status in ("completed", "failed") else "completed"
        run.status = status
        db_session.commit()
        if self.bus is not None:
            await self.bus.publish(CoreEvent(type=AGENT_FINISHED, trace_id=trace_id, payload={"run_id": run_id, "kind": run.kind, "status": status}))

    def live_agents(self, db_session=None) -> List[Dict[str, Any]]:
        rows = db_session.query(AgentRun).filter(AgentRun.status == "running").all()
        return [{"id": r.id, "kind": r.kind, "status": r.status} for r in rows]

    def _record_step(self, run_id: str, step, outcome, db_session, sequence: int) -> None:
        evidence = json.dumps(outcome.attempts[-1]["verifier"]) if outcome.attempts else "{}"
        db_session.add(
            AgentRunStep(
                id=token_id(),
                run_id=run_id,
                sequence=sequence,
                name=step.description or step.tool_name,
                status=outcome.status,
                attempt=len(outcome.attempts),
                detail_json=json.dumps({"tool": step.tool_name, "args": step.args}),
                evidence_json=evidence,
            )
        )
        db_session.commit()

    def _prior_agent_results(self, trace_id: Optional[str]) -> List[Dict[str, Any]]:
        if self.bus is None or not trace_id:
            return []
        finished = [e for e in self.bus.history(trace_id) if e.type == AGENT_FINISHED]
        return [{"run_id": e.payload.get("run_id"), "kind": e.payload.get("kind"), "status": e.payload.get("status")} for e in finished]
