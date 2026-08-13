# backend/app/api/eod.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.eod_memory import EndOfDayMemory

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eod", tags=["eod"])


@router.get("")
def build(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """End-of-day summary for the current user."""
    return EndOfDayMemory(db).build(user.id)


@router.post("/record")
def record(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Persist the end-of-day summary as an intel event (deduped per day)."""
    return {"recorded": EndOfDayMemory(db).record(user.id)}
