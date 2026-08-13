# backend/app/api/app_launcher.py
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.app_launcher import AppLauncher

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/apps", tags=["system"])


@router.get("/search")
def search_apps(q: str = "", user: User = Depends(get_current_user)):
    return {"query": q, "results": AppLauncher().search(q)}


@router.get("/suggest")
def suggest_apps(user: User = Depends(get_current_user)):
    return {"apps": AppLauncher().suggest()}
