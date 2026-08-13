# backend/app/api/privacy_scan.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.privacy_scanner import PrivacyScanner

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


@router.post("/scan")
def scan_privacy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PrivacyScanner(db).scan_report(current_user.id)
