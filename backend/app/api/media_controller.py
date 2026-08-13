# backend/app/api/media_controller.py
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.media_controller import MediaController

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/media", tags=["system"])


class MediaControlRequest(BaseModel):
    action: str


@router.post("")
def media_control(payload: MediaControlRequest, user: User = Depends(get_current_user)):
    return MediaController().control(payload.action)


@router.get("/now-playing")
def now_playing(user: User = Depends(get_current_user)):
    return MediaController().now_playing()
