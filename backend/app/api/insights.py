# backend/app/api/insights.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.insights import InsightEngine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("")
def list_insights(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    engine = InsightEngine(db)
    return {"insights": engine.insights(user.id)}
