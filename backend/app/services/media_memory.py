# backend/app/services/media_memory.py
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import MediaMemory, token_id, utcnow

log = logging.getLogger(__name__)

MEDIA_KINDS = {"image", "audio", "video"}


class MediaMemoryStore:
    def __init__(self, db) -> None:
        self.db = db

    def record(self, user_id: str, kind: str, *, caption: str = "", transcript: str = "", storage_path: str = "") -> MediaMemory:
        if kind not in MEDIA_KINDS:
            raise ValueError(f"invalid media kind: {kind}")
        row = MediaMemory(id=token_id(), user_id=user_id, kind=kind, caption=caption, transcript=transcript, storage_path=storage_path, created_at=utcnow())
        self.db.add(row)
        self.db.flush()
        return row

    def list(self, user_id: str, *, kind: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        stmt = select(MediaMemory).where(MediaMemory.user_id == user_id)
        if kind:
            stmt = stmt.where(MediaMemory.kind == kind)
        rows = self.db.scalars(stmt.order_by(MediaMemory.created_at.desc()).limit(limit)).all()
        return [
            {"id": r.id, "kind": r.kind, "caption": r.caption, "transcript": r.transcript, "storage_path": r.storage_path, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]

    def delete(self, user_id: str, memory_id: str) -> bool:
        r = self.db.get(MediaMemory, memory_id)
        if r is None or r.user_id != user_id:
            return False
        self.db.delete(r)
        return True
