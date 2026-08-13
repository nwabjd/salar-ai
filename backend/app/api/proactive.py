# backend/app/api/proactive.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.events import IntelEventStore
from ..services.intel.proactive import DETECTORS, ProactiveDetector

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/proactive", tags=["proactive"])

PROACTIVE_KINDS = [
    "low_storage", "upcoming_deadline", "unfinished_work",
    "failed_build", "high_cpu", "overdue_reminder",
]


@router.post("/scan")
def scan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Run all proactive detectors synchronously and report how many new events were recorded."""
    detected = ProactiveDetector(db).scan(user.id)
    db.commit()
    return {"detected": detected, "detectors": list(DETECTORS)}


@router.get("/recent")
def recent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Recent proactive intel events."""
    events = IntelEventStore(db).recent(user.id, kinds=PROACTIVE_KINDS, limit=50)
    return {"events": [IntelEventStore.to_dict(e) for e in events]}
