# backend/app/services/bookmarks.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from ..models import Bookmark, token_id, utcnow

log = logging.getLogger(__name__)


class BookmarkManager:
    def __init__(self, db) -> None:
        self.db = db

    def add(self, user_id: str, url: str, *, title: str = "", summary: str = "", tags: Optional[List[str]] = None) -> Bookmark:
        existing = self.db.scalar(select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.url == url))
        if existing:
            existing.title = title or existing.title
            existing.summary = summary or existing.summary
            existing.tags_json = json.dumps(tags or [])
            return existing
        bookmark = Bookmark(id=token_id(), user_id=user_id, url=url, title=title, summary=summary, tags_json=json.dumps(tags or []), created_at=utcnow())
        self.db.add(bookmark)
        self.db.flush()
        return bookmark

    def list(self, user_id: str, *, tag: Optional[str] = None, q: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        stmt = select(Bookmark).where(Bookmark.user_id == user_id)
        if tag:
            stmt = stmt.where(Bookmark.tags_json.like(f'%"{tag}"%'))
        if q:
            stmt = stmt.where(or_(Bookmark.title.ilike(f"%{q}%"), Bookmark.url.ilike(f"%{q}%"), Bookmark.summary.ilike(f"%{q}%")))
        rows = self.db.scalars(stmt.order_by(Bookmark.created_at.desc()).limit(limit)).all()
        return [
            {"id": b.id, "url": b.url, "title": b.title, "summary": b.summary, "tags": self._tags(b), "created_at": b.created_at.isoformat() if b.created_at else None}
            for b in rows
        ]

    def delete(self, user_id: str, bookmark_id: str) -> bool:
        b = self.db.get(Bookmark, bookmark_id)
        if b is None or b.user_id != user_id:
            return False
        self.db.delete(b)
        return True

    @staticmethod
    def _tags(b: Bookmark) -> list:
        try:
            return json.loads(b.tags_json or "[]")
        except Exception:
            return []
