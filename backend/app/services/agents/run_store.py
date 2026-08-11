import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...models import AgentRun, AgentRunStep


class AgentRunStore:
    def __init__(self, db: Session):
        self.db = db

    def start(self, user_id: str, conversation_id: Optional[str], kind: str, input_data: Any) -> AgentRun:
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
        detail: Optional[Any] = None,
        evidence: Optional[Any] = None,
        attempt: int = 1,
    ) -> AgentRunStep:
        step = AgentRunStep(
            run_id=run.id,
            name=name,
            status=status,
            attempt=attempt,
            detail_json=json.dumps({} if detail is None else detail),
            evidence_json=json.dumps([] if evidence is None else evidence),
        )
        self.db.add(step)
        self.db.flush()
        return step

    def complete(self, run: AgentRun, output: Any) -> AgentRun:
        run.status = "completed"
        run.output_json = json.dumps(output)
        run.error = ""
        self.db.flush()
        return run

    def fail(self, run: AgentRun, error: str) -> AgentRun:
        run.status = "failed"
        run.error = error[:1000]
        self.db.flush()
        return run
