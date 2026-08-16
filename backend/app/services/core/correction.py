# backend/app/services/core/correction.py
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .confidence import ConfidenceSystem
from .events import CORRECTION_ATTEMPT, CoreBus, CoreEvent
from .toolspec import ToolRegistry
from .verification import VerificationEngine

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class StepOutcome:
    step_id: str
    description: str
    status: str = "failed"
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    verified: bool = False
    confidence: float = 0.0
    result: Optional[Dict[str, Any]] = None


class SelfCorrectionLoop:
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        verifier: Optional[VerificationEngine] = None,
        confidence: Optional[ConfidenceSystem] = None,
        bus: Optional[CoreBus] = None,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.verifier = verifier or VerificationEngine()
        self.confidence = confidence or ConfidenceSystem()
        self.bus = bus
        self.max_attempts = max_attempts

    async def execute(self, step, user_id: str, db_session=None, trace_id: Optional[str] = None) -> StepOutcome:
        outcome = StepOutcome(step_id=getattr(step, "id", "step"), description=getattr(step, "description", ""))
        current_tool = step.tool_name
        current_args = dict(step.args)
        last_result: Optional[Dict[str, Any]] = None

        for attempt in range(1, self.max_attempts + 1):
            last_result = await self._run_tool(current_tool, current_args, user_id, db_session)
            vr = await self._verify(current_tool, current_args, last_result)
            outcome.attempts.append(
                {
                    "attempt": attempt,
                    "tool_name": current_tool,
                    "args": current_args,
                    "result": last_result,
                    "verifier": {"passed": vr.passed, "confidence": vr.confidence, "evidence": vr.evidence},
                }
            )
            if vr.passed:
                outcome.status = "completed"
                outcome.verified = True
                outcome.confidence = vr.confidence
                outcome.result = last_result
                return outcome

            if attempt < self.max_attempts:
                corrected = self._diagnose(current_tool, current_args, last_result)
                await self._notify_correction(trace_id, attempt, current_tool, current_args, corrected, vr.evidence)
                current_tool = corrected["tool_name"]
                current_args = corrected["args"]

        outcome.status = "failed"
        outcome.verified = False
        outcome.confidence = 0.0
        outcome.result = last_result
        return outcome

    async def _run_tool(self, tool_name: str, args: Dict[str, Any], user_id: str, db_session) -> Dict[str, Any]:
        try:
            return await self.registry.run(tool_name, args, user_id, db_session=db_session)
        except Exception as exc:
            log.warning("tool %s raised: %s", tool_name, exc)
            return {"error": str(exc)}

    async def _verify(self, tool_name: str, args: Dict[str, Any], result: Any):
        spec = self.registry.spec(tool_name)
        ctx = {"error": result.get("error") if isinstance(result, dict) else None}
        return await self.verifier.verify(spec, args, result, ctx)

    def _diagnose(self, tool_name: str, args: Dict[str, Any], result: Any) -> Dict[str, Any]:
        """Deterministic diagnosis: produce a corrected tool+args for the next attempt."""
        command = str(args.get("command", "")).strip()
        if tool_name == "run_command" and command.startswith("mkdir ") and " -p " not in command:
            return {"tool_name": tool_name, "args": {**args, "command": command.replace("mkdir ", "mkdir -p ", 1)}}
        return {"tool_name": tool_name, "args": args}

    async def _notify_correction(self, trace_id, attempt, tool_name, args, corrected, evidence) -> None:
        if self.bus is None:
            return
        await self.bus.publish(
            CoreEvent(
                type=CORRECTION_ATTEMPT,
                trace_id=trace_id,
                payload={"attempt": attempt, "tool_name": tool_name, "args": args, "corrected": corrected, "evidence": evidence},
            )
        )
