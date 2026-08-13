# backend/app/api/consent.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.consent import CONSENT_CATEGORIES, ConsentManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/consent", tags=["consent"])


class ConsentUpdate(BaseModel):
    category: str
    granted: bool
    note: str = ""


@router.get("")
def get_consent(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"consents": ConsentManager(db).snapshot(current_user.id)}


@router.post("")
def set_consent(
    body: ConsentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.category not in CONSENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"invalid consent category: {body.category}")
    cm = ConsentManager(db)
    cm.set(current_user.id, body.category, body.granted, note=body.note)
    db.commit()
    by_cat = {s["category"]: s for s in cm.snapshot(current_user.id)}
    return by_cat[body.category]
