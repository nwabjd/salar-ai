import json
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import AgentRun, AgentRunStep


class AgentRunStore:
    def __init__(self, db: Session):
        self.db = db

    def start(self, user_id: str, conversation_id: Optional[str], kind: str, input_data: Dict[str, Any]) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            kind=kind,
            status="running",
            input_json=json.dumps(input_data),
        )
        self.db.add(run)
        self.db.flush()
        return run

    def step(
        self,
        run: AgentRun,
        name: str,
        status: str,
        detail: Optional[Dict[str, Any]] = None,
        evidence: Optional[Iterable[Dict[str, Any]]] = None,
        attempt: int = 1,
    ) -> AgentRunStep:
        sequence = (
            self.db.query(func.max(AgentRunStep.sequence))
            .filter(AgentRunStep.run_id == run.id)
            .scalar()
            or 0
        ) + 1
        step = AgentRunStep(
            run_id=run.id,
            sequence=sequence,
            name=name,
            status=status,
            attempt=attempt,
            detail_json=json.dumps({} if detail is None else detail),
            evidence_json=json.dumps(list(evidence or [])),
        )
        self.db.add(step)
        self.db.flush()
        return step

    def complete(self, run: AgentRun, output: Dict[str, Any]) -> None:
        run.status = "completed"
        run.output_json = json.dumps(output)
        run.error = ""
        self.db.flush()

    def fail(self, run: AgentRun, error: str) -> None:
        run.status = "failed"
        run.error = error[:1000]
        self.db.flush()
