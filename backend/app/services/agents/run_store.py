import json
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...models import AgentRun, AgentRunStep, Conversation


class AgentRunStore:
    TERMINAL_STATUSES = {"completed", "partial", "failed", "cancelled"}

    def __init__(self, db: Session):
        self.db = db

    def start(self, user_id: str, conversation_id: Optional[str], kind: str, input_data: Dict[str, Any]) -> AgentRun:
        if conversation_id is not None:
            conversation = (
                self.db.query(Conversation)
                .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                .first()
            )
            if conversation is None:
                raise ValueError("Conversation does not belong to user")
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
        result = self.db.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id)
            .values(next_step_sequence=AgentRun.next_step_sequence + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ValueError("Agent run does not exist")
        sequence = self.db.execute(
            select(AgentRun.next_step_sequence).where(AgentRun.id == run.id)
        ).scalar_one() - 1
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
        self.finalize(run, "completed", output=output)

    def fail(self, run: AgentRun, error: str) -> None:
        self.finalize(run, "failed", error=error)

    def finalize(
        self,
        run: AgentRun,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error: str = "",
    ) -> None:
        if status not in self.TERMINAL_STATUSES:
            raise ValueError(f"Unsupported terminal status: {status}")
        run.status = status
        if output is not None:
            run.output_json = json.dumps(output)
        run.error = error[:1000]
        self.db.flush()
