# backend/app/services/contact_intel.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import ContactInteraction, ContactProfile, token_id, utcnow

log = logging.getLogger(__name__)

INTERACTION_KINDS = {"conversation", "meeting", "project", "follow_up", "note"}


class ContactIntelligence:
    def __init__(self, db) -> None:
        self.db = db

    def upsert(self, user_id: str, name: str, *, email: str = "", phone: str = "", notes: str = "") -> ContactProfile:
        profile = self.find_by_name(user_id, name)
        if profile is None:
            profile = ContactProfile(id=token_id(), user_id=user_id, name=name, email=email, phone=phone, notes=notes, created_at=utcnow(), updated_at=utcnow())
            self.db.add(profile)
            self.db.flush()
        else:
            if email:
                profile.email = email
            if phone:
                profile.phone = phone
            if notes:
                profile.notes = notes
        return profile

    def find_by_name(self, user_id: str, name: str) -> Optional[ContactProfile]:
        return self.db.scalar(select(ContactProfile).where(ContactProfile.user_id == user_id, ContactProfile.name == name))

    def list_profiles(self, user_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.db.scalars(select(ContactProfile).where(ContactProfile.user_id == user_id).order_by(ContactProfile.updated_at.desc()).limit(limit)).all()
        return [self._profile_dict(r) for r in rows]

    def record_interaction(self, user_id: str, contact_name: str, kind: str, detail: Optional[Dict[str, Any]] = None) -> ContactInteraction:
        if kind not in INTERACTION_KINDS:
            raise ValueError(f"invalid interaction kind: {kind}")
        profile = self.upsert(user_id, contact_name)
        interaction = ContactInteraction(id=token_id(), user_id=user_id, contact_id=profile.id, kind=kind, detail_json=json.dumps(detail or {}), created_at=utcnow())
        self.db.add(interaction)
        self.db.flush()
        profile.updated_at = utcnow()
        return interaction

    def brief(self, user_id: str, contact_id: str) -> Dict[str, Any]:
        profile = self.db.get(ContactProfile, contact_id)
        if profile is None or profile.user_id != user_id:
            raise ValueError("contact not found")
        interactions = self.db.scalars(
            select(ContactInteraction).where(ContactInteraction.contact_id == contact_id).order_by(ContactInteraction.created_at.desc()).limit(50)
        ).all()
        return {
            **self._profile_dict(profile),
            "interactions": [
                {"id": i.id, "kind": i.kind, "detail": json.loads(i.detail_json or "{}"), "created_at": i.created_at.isoformat() if i.created_at else None}
                for i in interactions
            ],
            "pending_follow_ups": [
                {"id": i.id, "detail": json.loads(i.detail_json or "{}")}
                for i in interactions if i.kind == "follow_up"
            ],
        }

    def _profile_dict(self, r: ContactProfile) -> Dict[str, Any]:
        return {
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "phone": r.phone,
            "notes": r.notes,
            "tags": self._tags(r),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    @staticmethod
    def _tags(r: ContactProfile) -> list:
        try:
            return json.loads(r.tags_json or "[]")
        except Exception:
            return []
