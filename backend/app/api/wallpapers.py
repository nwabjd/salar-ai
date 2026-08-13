# backend/app/api/wallpapers.py
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.wallpapers import WallpaperManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wallpapers", tags=["wallpapers"])


def _manager(request: Request):
    settings = getattr(request.app.state, "settings", None)
    storage_dir = getattr(settings, "storage_dir", None) if settings else None
    if storage_dir is None:
        raise HTTPException(status_code=503, detail="storage not configured")
    return WallpaperManager(storage_dir)


@router.get("")
def list_wallpapers(request: Request, user: User = Depends(get_current_user)):
    return {"wallpapers": _manager(request).list()}


@router.post("")
async def upload_wallpaper(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    user: User = Depends(get_current_user),
):
    data = await file.read()
    return _manager(request).save(data, name=name)
