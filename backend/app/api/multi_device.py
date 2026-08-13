# backend/app/api/multi_device.py
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.multi_device import MultiDevice
from ..services.whatsapp import WhatsAppClient

log = logging.getLogger(__name__)

router = APIRouter(tags=["multi-device"])


class SyncRequest(BaseModel):
    device_id: str


class RemoteRequest(BaseModel):
    action: str
    payload: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False


class PushRegisterRequest(BaseModel):
    token: str
    platform: str
    device_id: Optional[str] = None


class MessagingSendRequest(BaseModel):
    channel: str
    to: str
    text: str


@router.post("/api/devices/sync")
def device_sync(payload: SyncRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    md = MultiDevice(db)
    try:
        state = md.touch(user.id, payload.device_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Device not found")
    db.commit()
    return {
        "device_id": state.device_id,
        "last_synced_at": state.last_synced_at.isoformat() if state.last_synced_at else None,
        "pending_commands": state.pending_commands,
    }


@router.get("/api/devices/pending")
def pending_commands(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"commands": MultiDevice(db).pending_for(user.id, device_id)}


@router.get("/api/devices/sync/status")
def sync_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"devices": MultiDevice(db).sync_status(user.id)}


@router.get("/api/devices/offline")
def offline_devices(minutes: int = 5, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"devices": MultiDevice(db).offline_since(user.id, minutes=max(minutes, 1))}


@router.post("/api/devices/{device_id}/remote")
def remote_action(device_id: str, payload: RemoteRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = MultiDevice(db).remote(user.id, device_id, payload.action, payload.payload, requires_confirmation=payload.requires_confirmation)
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["detail"])
    db.commit()
    return result


@router.post("/api/push/register")
def push_register(payload: PushRegisterRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pt = MultiDevice(db).register_push(user.id, payload.token, payload.platform, device_id=payload.device_id)
    db.commit()
    return {"id": pt.id, "platform": pt.platform, "token": pt.token, "device_id": pt.device_id}


@router.get("/api/push/tokens")
def push_tokens(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"tokens": MultiDevice(db).list_push_tokens(user.id)}


@router.delete("/api/push/tokens/{token_id}")
def push_unregister(token_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not MultiDevice(db).unregister_push(user.id, token_id):
        raise HTTPException(status_code=404, detail="Push token not found")
    db.commit()
    return {"status": "ok"}


@router.post("/api/messaging/send")
async def messaging_send(payload: MessagingSendRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await MultiDevice(db).send_via(user.id, payload.channel, payload.to, payload.text)


@router.get("/api/messaging/status")
async def messaging_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    client = WhatsAppClient()
    try:
        return await client.get_status(user.id)
    finally:
        await client.close()
