# backend/app/api/predictive.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.predictive import PredictiveEngine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictive", tags=["predictive"])


@router.get("")
def patterns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Repeated tool-usage patterns for the current user."""
    return {"patterns": PredictiveEngine(db).patterns(user.id)}


@router.get("/now")
def now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Suggestions for actions the user normally takes at this hour."""
    return {"suggestions": PredictiveEngine(db).suggest_now(user.id)}
