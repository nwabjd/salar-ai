# backend/app/services/intel/dynamic_memory.py
import logging
import re
from typing import Any, Dict, List

from sqlalchemy import select

from ...models import Memory

log = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


class DynamicMemory:
    def __init__(self, db) -> None:
        self.db = db

    def find_duplicates(self, user_id: str, *, threshold: float = 0.9) -> List[Dict[str, Any]]:
        """Find memory pairs with near-identical titles (token overlap >= threshold)."""
        memories = self.db.scalars(select(Memory).where(Memory.user_id == user_id)).all()
        pairs = []
        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                a, b = memories[i], memories[j]
                if self._overlap(a.title, b.title) >= threshold:
                    pairs.append({"a_id": a.id, "b_id": b.id, "a_title": a.title, "b_title": b.title, "overlap": self._overlap(a.title, b.title)})
        return pairs

    def merge(self, user_id: str, keep_id: str, drop_id: str) -> bool:
        keep = self.db.get(Memory, keep_id)
        drop = self.db.get(Memory, drop_id)
        if keep is None or drop is None or keep.user_id != user_id or drop.user_id != user_id:
            return False
        if keep.id == drop.id:
            return False
        keep.content = f"{keep.content}\n\n[merged from '{drop.title}']\n{drop.content}"
        self.db.delete(drop)
        return True

    def prune_old(self, user_id: str, *, max_age_days: int = 365, keep_recent: int = 20) -> int:
        """Delete very old memories beyond the recent N, in the 'ephemeral' layer."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        rows = self.db.scalars(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.layer == "ephemeral",
                Memory.updated_at < cutoff,
            ).order_by(Memory.updated_at.desc())
        ).all()
        victims = rows[keep_recent:]
        for m in victims:
            self.db.delete(m)
        return len(victims)

    @staticmethod
    def _overlap(a: str, b: str) -> float:
        ta = set(_norm(a).split())
        tb = set(_norm(b).split())
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / min(len(ta), len(tb))
