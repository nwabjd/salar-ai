# backend/app/services/missions/events.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import MissionEvent, token_id, utcnow

log = logging.getLogger(__name__)


class MissionEventStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def append(self, mission_id: str, kind: str, detail: Optional[Dict[str, Any]] = None) -> MissionEvent:
        seq = (self.db.scalar(
            select(func.max(MissionEvent.sequence)).where(MissionEvent.mission_id == mission_id)
        ) or 0) + 1
        ev = MissionEvent(
            id=token_id(),
            mission_id=mission_id,
            sequence=seq,
            kind=kind,
            detail_json=json.dumps(detail or {}),
            created_at=utcnow(),
        )
        self.db.add(ev)
        return ev

    def recent(self, mission_id: str, *, limit: int = 50, since_sequence: Optional[int] = None) -> List[MissionEvent]:
        stmt = select(MissionEvent).where(MissionEvent.mission_id == mission_id)
        if since_sequence is not None:
            stmt = stmt.where(MissionEvent.sequence > since_sequence)
        stmt = stmt.order_by(MissionEvent.sequence.asc()).limit(limit)
        return list(self.db.scalars(stmt).all())
