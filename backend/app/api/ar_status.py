# backend/app/api/ar_status.py
import logging

from fastapi import APIRouter, Depends

from ..models import User
from ..security import get_current_user
from ..services.ar_status import ARStatus

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ar", tags=["ar"])


@router.get("/status")
def ar_status(user: User = Depends(get_current_user)):
    return ARStatus().check()
