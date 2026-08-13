# backend/app/api/file_organizer.py
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.file_organizer import FileOrganizer

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["file-organizer"])


def _resolve_dir(request: Request, path: str = "") -> Path:
    target = Path(path) if path else request.app.state.settings.storage_dir
    if not target.is_absolute():
        raise HTTPException(status_code=400, detail="path must be an absolute path")
    return target


@router.get("/organize/plan")
def organize_plan(path: str = "", request: Request = None, user: User = Depends(get_current_user)):
    return {"plan": FileOrganizer(_resolve_dir(request, path)).plan()}


@router.post("/organize/apply")
def organize_apply(path: str = "", request: Request = None, user: User = Depends(get_current_user)):
    result = FileOrganizer(_resolve_dir(request, path)).apply()
    return {"status": "ok" if not result["errors"] else "partial", **result}
