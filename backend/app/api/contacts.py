# backend/app/api/contacts.py
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..database import get_db
from ..security import get_current_user
from ..services.contact_intel import ContactIntelligence, INTERACTION_KINDS
from ..models import User

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ContactUpsertBody(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    notes: str = ""


class InteractionBody(BaseModel):
    kind: str
    detail: dict = Field(default_factory=dict)


@router.get("")
def list_contacts(user=Depends(get_current_user), db=Depends(get_db)):
    return {"contacts": ContactIntelligence(db).list_profiles(user.id)}


@router.post("", status_code=status.HTTP_200_OK)
def upsert_contact(body: ContactUpsertBody, user=Depends(get_current_user), db=Depends(get_db)):
    profile = ContactIntelligence(db).upsert(user.id, body.name, email=body.email, phone=body.phone, notes=body.notes)
    db.commit()
    return ContactIntelligence(db)._profile_dict(profile)


@router.get("/{contact_id}")
def contact_brief(contact_id: str, user=Depends(get_current_user), db=Depends(get_db)):
    try:
        return ContactIntelligence(db).brief(user.id, contact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{contact_id}/interactions", status_code=status.HTTP_200_OK)
def record_interaction(contact_id: str, body: InteractionBody, user=Depends(get_current_user), db=Depends(get_db)):
    ci = ContactIntelligence(db)
    try:
        brief = ci.brief(user.id, contact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.kind not in INTERACTION_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid interaction kind: {body.kind}")
    interaction = ci.record_interaction(user.id, brief["name"], body.kind, body.detail)
    db.commit()
    return {
        "id": interaction.id,
        "kind": interaction.kind,
        "detail": interaction.detail_json,
        "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
    }
