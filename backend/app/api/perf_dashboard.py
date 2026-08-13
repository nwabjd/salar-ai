# backend/app/api/perf_dashboard.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.perf_dashboard import PerformanceDashboard

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/perf", tags=["system"])


@router.get("")
def perf_snapshot(user: User = Depends(get_current_user)):
    return PerformanceDashboard().snapshot()
