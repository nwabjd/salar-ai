# backend/app/services/thought_stream.py
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ActionLog, AgentRun, AgentRunStep, IntelEvent, Mission, MissionEvent


SOURCE_RANK = {"agent": 0, "mission": 1, "action": 2, "intel": 3}


def _loads(raw: str):
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}


class ThoughtStream:
    """Operational stream of what SALAR is doing for a user.

    Merge-sorts agent steps, mission events, tool actions, and intel notices
    into a single real-time feed. This is an operational log of actions taken,
    not private chain-of-thought.
    """

    def __init__(self, db: Session):
        self.db = db

    def stream(self, user_id: str, *, limit: int = 50, source: str = None) -> list[dict]:
        sources = (
            [source] if source else ["agent", "mission", "action", "intel"]
        )
        items = []
        if "agent" in sources:
            items.extend(self._agent_steps(user_id))
        if "mission" in sources:
            items.extend(self._mission_events(user_id))
        if "action" in sources:
            items.extend(self._actions(user_id))
        if "intel" in sources:
            items.extend(self._intel(user_id))

        items.sort(key=lambda i: (i["created_at"], SOURCE_RANK[i["source"]]), reverse=True)
        return items[:limit]

    def _agent_steps(self, user_id: str) -> list[dict]:
        rows = self.db.execute(
            select(AgentRunStep, AgentRun)
            .join(AgentRun, AgentRun.id == AgentRunStep.run_id)
            .where(AgentRun.user_id == user_id)
        ).all()
        items = []
        for step, run in rows:
            if run.status == "completed":
                prefix = "✓ "
            elif run.status == "running":
                prefix = "→ "
            else:
                prefix = ""
            items.append({
                "seq": step.id,
                "kind": "agent_step",
                "title": f"{prefix}{step.name}",
                "detail": _loads(step.detail_json),
                "source": "agent",
                "created_at": step.created_at,
            })
        return items

    def _mission_events(self, user_id: str) -> list[dict]:
        rows = self.db.execute(
            select(MissionEvent, Mission)
            .join(Mission, Mission.id == MissionEvent.mission_id)
            .where(Mission.user_id == user_id)
        ).all()
        return [
            {
                "seq": event.id,
                "kind": "mission",
                "title": event.kind,
                "detail": _loads(event.detail_json),
                "source": "mission",
                "created_at": event.created_at,
            }
            for event, _mission in rows
        ]

    def _actions(self, user_id: str) -> list[dict]:
        rows = self.db.scalars(
            select(ActionLog).where(ActionLog.user_id == user_id)
        ).all()
        return [
            {
                "seq": action.id,
                "kind": "action",
                "title": f"{action.tool} executed",
                "detail": _loads(action.result_json),
                "source": "action",
                "created_at": action.created_at,
            }
            for action in rows
        ]

    def _intel(self, user_id: str) -> list[dict]:
        rows = self.db.scalars(
            select(IntelEvent).where(IntelEvent.user_id == user_id)
        ).all()
        return [
            {
                "seq": event.id,
                "kind": "intel",
                "title": event.title,
                "detail": event.summary,
                "source": "intel",
                "created_at": event.created_at,
            }
            for event in rows
        ]
