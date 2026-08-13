# backend/app/api/device_automation.py
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.system.device_automation import DeviceAutomation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system/devices", tags=["system"])


class DeviceCommandRequest(BaseModel):
    kind: str
    payload: dict = None
    requires_confirmation: bool = False


@router.get("")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"devices": DeviceAutomation(db).list(user.id)}


@router.get("/commands/history")
def command_history(limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"commands": DeviceAutomation(db).history(user.id, limit=min(max(limit, 1), 100))}


@router.post("/{device_id}/command")
def issue_command(device_id: str, payload: DeviceCommandRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return DeviceAutomation(db).issue(user.id, device_id, payload.kind, payload.payload, requires_confirmation=payload.requires_confirmation)
