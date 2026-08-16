# backend/app/services/core/events.py
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from ...models import CoreEventLog, token_id

log = logging.getLogger(__name__)

TASK_STARTED = "TASK_STARTED"
TASK_PLANNED = "TASK_PLANNED"
AGENT_SPAWNED = "AGENT_SPAWNED"
AGENT_STEP = "AGENT_STEP"
AGENT_FINISHED = "AGENT_FINISHED"
TOOL_CALLED = "TOOL_CALLED"
TOOL_RESULT = "TOOL_RESULT"
VERIFICATION_PASSED = "VERIFICATION_PASSED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"
CORRECTION_ATTEMPT = "CORRECTION_ATTEMPT"
TASK_COMPLETED = "TASK_COMPLETED"
TASK_FAILED = "TASK_FAILED"
TASK_APPROVED = "TASK_APPROVED"
TASK_DENIED = "TASK_DENIED"
SUPERVISOR_ALERT = "SUPERVISOR_ALERT"

ALL_EVENTS = [
    TASK_STARTED,
    TASK_PLANNED,
    AGENT_SPAWNED,
    AGENT_STEP,
    AGENT_FINISHED,
    TOOL_CALLED,
    TOOL_RESULT,
    VERIFICATION_PASSED,
    VERIFICATION_FAILED,
    CORRECTION_ATTEMPT,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_APPROVED,
    TASK_DENIED,
    SUPERVISOR_ALERT,
]


class CoreEvent(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CoreBus:
    """Typed async pub/sub. Every published event is journaled (durable) then dispatched."""

    def __init__(self, db_factory: Optional[Callable[[], Any]] = None) -> None:
        self._db_factory = db_factory
        self._subscribers: Dict[str, List[Callable[[CoreEvent], Any]]] = {}
        self._published_count = 0

    def subscribe(self, event_type: str, handler: Callable[[CoreEvent], Any]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def publish(self, event: CoreEvent) -> None:
        self._published_count += 1
        await self.journal(event)
        for handler in self._subscribers.get(event.type, []):
            try:
                result = handler(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                log.exception("subscriber error for %s", event.type)

    async def journal(self, event: CoreEvent) -> None:
        if self._db_factory is None:
            return
        db = None
        try:
            db = self._db_factory()
            db.add(
                CoreEventLog(
                    id=token_id(),
                    trace_id=event.trace_id,
                    event_type=event.type,
                    payload=json.dumps(event.payload, default=str),
                )
            )
            db.commit()
        except Exception:
            log.exception("failed to journal event %s", event.type)
        finally:
            if db is not None:
                db.close()

    def history(self, trace_id: str) -> List[CoreEvent]:
        if self._db_factory is None:
            return []
        db = self._db_factory()
        try:
            rows = db.query(CoreEventLog).filter(CoreEventLog.trace_id == trace_id).order_by(CoreEventLog.created_at).all()
            return [
                CoreEvent(
                    type=r.event_type,
                    payload=json.loads(r.payload or "{}"),
                    trace_id=r.trace_id,
                    created_at=r.created_at,
                )
                for r in rows
            ]
        except Exception:
            log.exception("failed to read history for trace %s", trace_id)
            return []
        finally:
            db.close()

    @property
    def published_count(self) -> int:
        return self._published_count
