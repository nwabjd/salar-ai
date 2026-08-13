# backend/app/services/consent.py
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import Consent, token_id, utcnow

log = logging.getLogger(__name__)

CONSENT_CATEGORIES = ["voice", "camera", "screen", "location", "emails", "whatsapp", "analytics"]


class ConsentManager:
    def __init__(self, db) -> None:
        self.db = db

    def set(self, user_id: str, category: str, granted: bool, *, note: str = "") -> Consent:
        if category not in CONSENT_CATEGORIES:
            raise ValueError(f"invalid consent category: {category}")
        row = self.get(user_id, category)
        if row is None:
            row = Consent(id=token_id(), user_id=user_id, category=category, granted=granted, note=note, created_at=utcnow(), updated_at=utcnow())
            self.db.add(row)
            self.db.flush()
        else:
            row.granted = granted
            row.note = note or row.note
        return row

    def get(self, user_id: str, category: str) -> Optional[Consent]:
        return self.db.scalar(select(Consent).where(Consent.user_id == user_id, Consent.category == category))

    def granted(self, user_id: str, category: str) -> bool:
        row = self.get(user_id, category)
        return bool(row and row.granted)

    def snapshot(self, user_id: str) -> List[Dict[str, Any]]:
        rows = {r.category: r for r in self.db.scalars(select(Consent).where(Consent.user_id == user_id)).all()}
        return [
            {"category": c, "granted": rows[c].granted if c in rows else False, "note": rows[c].note if c in rows else "", "configured": c in rows}
            for c in CONSENT_CATEGORIES
        ]
