"""Intel event ledger — the single place background intelligence is recorded.

The ledger is passive: SALAR never pushes these events into a chat. They are
surfaced only when the user asks (morning brief, "anything important?", intel
dashboard). Entries expire so the table doesn't grow forever.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...models import IntelEvent
from ..jobs.store import utcnow

log = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 14 * 24 * 3600  # 14 days


class IntelEventStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- writes ----

    def record(
        self,
        *,
        user_id: str,
        kind: str,
        severity: str,
        title: str,
        summary: str = "",
        source: str = "",
        detail: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> IntelEvent:
        event = IntelEvent(
            user_id=user_id,
            kind=kind,
            severity=severity,
            title=title[:300],
            summary=summary,
            source=source,
            detail_json=json.dumps(detail or {}),
            evidence_json=json.dumps(evidence or []),
            expires_at=utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds else None,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def ack(self, event_id: str, user_id: str) -> bool:
        event = self.db.get(IntelEvent, event_id)
        if event is None or event.user_id != user_id:
            return False
        event.is_read = True
        return True

    def ack_all(self, user_id: str) -> int:
        rows = self.db.scalars(
            select(IntelEvent).where(IntelEvent.user_id == user_id, IntelEvent.is_read.is_(False))
        ).all()
        for row in rows:
            row.is_read = True
        return len(rows)

    def purge_expired(self) -> int:
        rows = self.db.scalars(select(IntelEvent).where(IntelEvent.expires_at.isnot(None), IntelEvent.expires_at < utcnow())).all()
        for row in rows:
            self.db.delete(row)
        return len(rows)

    # ---- reads ----

    def recent(
        self,
        user_id: str,
        *,
        kinds: Optional[List[str]] = None,
        unread_only: bool = False,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[IntelEvent]:
        statement = select(IntelEvent).where(IntelEvent.user_id == user_id)
        if kinds:
            statement = statement.where(IntelEvent.kind.in_(kinds))
        if unread_only:
            statement = statement.where(IntelEvent.is_read.is_(False))
        if severity:
            statement = statement.where(IntelEvent.severity == severity)
        statement = statement.order_by(IntelEvent.created_at.desc()).limit(limit)
        return list(self.db.scalars(statement).all())

    def unread_count(self, user_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(IntelEvent.id)).where(
                    IntelEvent.user_id == user_id,
                    IntelEvent.is_read.is_(False),
                )
            )
            or 0
        )

    def get(self, event_id: str) -> Optional[IntelEvent]:
        return self.db.get(IntelEvent, event_id)

    # ---- serialization ----

    @staticmethod
    def to_dict(event: IntelEvent) -> Dict[str, Any]:
        return {
            "id": event.id,
            "kind": event.kind,
            "severity": event.severity,
            "source": event.source,
            "title": event.title,
            "summary": event.summary,
            "detail": _load_json(event.detail_json),
            "evidence": _load_json(event.evidence_json, default=list),
            "is_read": event.is_read,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "expires_at": event.expires_at.isoformat() if event.expires_at else None,
        }


def _load_json(raw: str, default=dict):
    try:
        value = json.loads(raw or "{}")
        return value
    except (TypeError, ValueError):
        return default()
