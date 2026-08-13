# backend/app/api/audio_intel.py
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.audio_intel import AudioIntelligence

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/audio", tags=["system"])


class VolumeRequest(BaseModel):
    level: int


@router.get("/devices")
def audio_devices(user: User = Depends(get_current_user)):
    return {"devices": AudioIntelligence().devices()}


@router.post("/volume")
def set_volume(payload: VolumeRequest, user: User = Depends(get_current_user)):
    return AudioIntelligence().set_volume(payload.level)
