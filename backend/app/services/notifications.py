# backend/app/services/notifications.py
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import Notification, token_id, utcnow

log = logging.getLogger(__name__)


class NotificationCenter:
    def __init__(self, db) -> None:
        self.db = db

    def push(self, user_id: str, kind: str, title: str, *, body: str = "", link: str = "", severity: str = "info") -> Notification:
        n = Notification(id=token_id(), user_id=user_id, kind=kind, title=title[:300], body=body, link=link, severity=severity, is_read=False, created_at=utcnow())
        self.db.add(n)
        self.db.flush()
        return n

    def list(self, user_id: str, *, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        rows = self.db.scalars(stmt.order_by(Notification.created_at.desc()).limit(limit)).all()
        return [self._serialize(n) for n in rows]

    def mark_read(self, user_id: str, notification_id: str) -> bool:
        n = self.db.get(Notification, notification_id)
        if n is None or n.user_id != user_id:
            return False
        n.is_read = True
        return True

    def mark_all_read(self, user_id: str) -> int:
        rows = self.db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False))).all()
        for r in rows:
            r.is_read = True
        return len(rows)

    def unread_count(self, user_id: str) -> int:
        return len(self.list(user_id, unread_only=True))

    def _serialize(self, n: Notification) -> Dict[str, Any]:
        return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "severity": n.severity, "is_read": n.is_read, "created_at": n.created_at.isoformat() if n.created_at else None}
