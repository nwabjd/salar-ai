# backend/app/services/core/supervisor.py
import json
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .events import (
    AGENT_FINISHED,
    SUPERVISOR_ALERT,
    TOOL_CALLED,
    TOOL_RESULT,
    VERIFICATION_FAILED,
    CoreBus,
    CoreEvent,
)
from .toolspec import ToolRegistry

log = logging.getLogger(__name__)

LOOP_THRESHOLD = 3
FAILURE_CASCADE_THRESHOLD = 2
TOKEN_SPIKE_THRESHOLD = 50 * 1024
TOKEN_SPIKE_WINDOW = 3
CONFLICT_DISSIMILARITY = 0.7
CONFLICT_CONFIDENCE = 0.7
RISKY_RISK_LEVEL = 3


@dataclass(frozen=True)
class SupervisorAlert:
    rule: str
    trace_id: Optional[str]
    message: str
    severity: str

    def to_dict(self) -> Dict[str, Any]:
        return {"rule": self.rule, "trace_id": self.trace_id, "message": self.message, "severity": self.severity}


def _content_dissimilarity(a: Any, b: Any) -> float:
    """1 - simple word-set overlap ratio between two result strings."""
    if a == b:
        return 0.0
    ta = set(str(a or "").lower().split())
    tb = set(str(b or "").lower().split())
    if not ta or not tb:
        return 1.0
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return 1.0 - overlap


class Supervisor:
    """Watches the event bus and raises SupervisorAlert for anomalous traces.

    State is per-trace so concurrent tasks never interfere. Each rule fires at
    most once per (rule, trace_id) to avoid alert spam on a continuous stream.
    """

    def __init__(self, bus: Optional[CoreBus] = None, registry: Optional[ToolRegistry] = None) -> None:
        self.bus = bus
        self.registry = registry or ToolRegistry()
        self.alerts: List[SupervisorAlert] = []
        self._tool_calls: Dict[str, Dict[str, int]] = {}
        self._failures: Dict[str, int] = {}
        self._finished: Dict[str, List[Dict[str, Any]]] = {}
        self._tool_results: Dict[str, deque] = {}
        self._approved: set = set()
        self._fired: set = set()

    def subscribe_to(self, bus: CoreBus) -> None:
        self.bus = bus
        for event_type in (TOOL_CALLED, TOOL_RESULT, VERIFICATION_FAILED, AGENT_FINISHED):
            bus.subscribe(event_type, self.watch)

    async def watch(self, event: CoreEvent) -> Optional[SupervisorAlert]:
        """Process a single event; return the alert raised, if any."""
        trace_id = event.trace_id or "__global__"
        if event.type in ("TASK_APPROVED", "TASK_DENIED") or "APPROV" in event.type.upper():
            self._approved.add(trace_id)

        alert = None
        if event.type == TOOL_CALLED:
            alert = self._on_tool_called(event, trace_id)
        elif event.type == TOOL_RESULT:
            alert = self._on_tool_result(event, trace_id)
        elif event.type == VERIFICATION_FAILED:
            alert = self._on_verification_failed(event, trace_id)
        elif event.type == AGENT_FINISHED:
            alert = self._on_agent_finished(event, trace_id)

        if alert is not None:
            key = (alert.rule, trace_id)
            if key not in self._fired:
                self._fired.add(key)
                self.alerts.append(alert)
                if self.bus is not None:
                    await self.bus.publish(
                        CoreEvent(type=SUPERVISOR_ALERT, trace_id=event.trace_id, payload=alert.to_dict())
                    )
                return alert
        return None

    def _on_tool_called(self, event: CoreEvent, trace_id: str) -> Optional[SupervisorAlert]:
        tool = event.payload.get("tool", "")
        args = event.payload.get("args", {})
        key = f"{tool}|{json.dumps(args, sort_keys=True, default=str)}"
        calls = self._tool_calls.setdefault(trace_id, {})
        calls[key] = calls.get(key, 0) + 1
        if calls[key] >= LOOP_THRESHOLD:
            return SupervisorAlert(
                rule="loop",
                trace_id=event.trace_id,
                message=f"tool '{tool}' called {calls[key]}x with identical args in one trace",
                severity="warning",
            )
        spec = self.registry.spec(tool)
        if spec.risk_level >= RISKY_RISK_LEVEL and trace_id not in self._approved:
            return SupervisorAlert(
                rule="dangerous_action",
                trace_id=event.trace_id,
                message=f"risky tool '{tool}' (risk {spec.risk_level}) invoked without prior approval",
                severity="critical",
            )
        return None

    def _on_tool_result(self, event: CoreEvent, trace_id: str) -> Optional[SupervisorAlert]:
        size = len(json.dumps(event.payload, default=str).encode("utf-8"))
        window = self._tool_results.setdefault(trace_id, deque(maxlen=TOKEN_SPIKE_WINDOW))
        window.append(size)
        if len(window) == TOKEN_SPIKE_WINDOW and (sum(window) / len(window)) > TOKEN_SPIKE_THRESHOLD:
            return SupervisorAlert(
                rule="token_spike",
                trace_id=event.trace_id,
                message=f"average TOOL_RESULT payload size {sum(window) // len(window)} bytes exceeds {TOKEN_SPIKE_THRESHOLD}",
                severity="warning",
            )
        return None

    def _on_verification_failed(self, event: CoreEvent, trace_id: str) -> Optional[SupervisorAlert]:
        self._failures[trace_id] = self._failures.get(trace_id, 0) + 1
        if self._failures[trace_id] >= FAILURE_CASCADE_THRESHOLD:
            return SupervisorAlert(
                rule="failure_cascade",
                trace_id=event.trace_id,
                message=f"{self._failures[trace_id]} verification failures on one trace",
                severity="warning",
            )
        return None

    def _on_agent_finished(self, event: CoreEvent, trace_id: str) -> Optional[SupervisorAlert]:
        results = self._finished.setdefault(trace_id, [])
        current = {"result": event.payload.get("result", ""), "confidence": float(event.payload.get("confidence", 0.0))}
        for prev in results:
            if _content_dissimilarity(prev["result"], current["result"]) > CONFLICT_DISSIMILARITY and (
                prev["confidence"] < CONFLICT_CONFIDENCE or current["confidence"] < CONFLICT_CONFIDENCE
            ):
                return SupervisorAlert(
                    rule="conflict",
                    trace_id=event.trace_id,
                    message="two agents returned dissimilar low-confidence results on one trace",
                    severity="warning",
                )
        results.append(current)
        return None
