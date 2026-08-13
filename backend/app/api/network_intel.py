# backend/app/api/network_intel.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.network_intel import NetworkIntelligence

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/network", tags=["system"])


@router.get("")
def network_local_info(user: User = Depends(get_current_user)):
    return NetworkIntelligence().local_info()


@router.get("/ping")
def network_ping(host: str = "8.8.8.8", user: User = Depends(get_current_user)):
    return NetworkIntelligence().ping(host)
