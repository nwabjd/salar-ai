import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Command, Device, User
from ..schemas import CommandCreate, CommandResponse, CommandResult, DeviceCreate, DeviceRegistration, DeviceResponse
from ..security import get_current_user


router = APIRouter(tags=["devices"])
ALLOWED_COMMANDS = {"open_url", "open_app", "reveal_path", "create_directory", "system_info", "notification"}
CONFIRMATION_REQUIRED = {"reveal_path", "create_directory"}


def _ingest_device(device: Device, db: Session) -> None:
    """Mirror a device heartbeat into the world graph (best-effort)."""
    try:
        from ..services.world_model import WorldGraph, WorldIngestor
        graph = WorldGraph(db)
        WorldIngestor(graph).ingest_device(device.user_id, {
            "name": device.name,
            "id": device.id,
            "platform": device.platform or "",
        })
        db.commit()
    except Exception:
        db.rollback()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _command_response(command: Command) -> CommandResponse:
    return CommandResponse(
        id=command.id, device_id=command.device_id, kind=command.kind,
        payload=json.loads(command.payload_json), status=command.status,
        result=json.loads(command.result_json) if command.result_json else None,
        requires_confirmation=command.requires_confirmation, created_at=command.created_at,
        completed_at=command.completed_at,
    )


@router.post("/api/devices", response_model=DeviceRegistration, status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    device = Device(user_id=user.id, name=payload.name, platform=payload.platform, token_hash=_digest(token))
    db.add(device)
    db.commit()
    db.refresh(device)
    base = DeviceResponse.model_validate(device, from_attributes=True)
    return DeviceRegistration(**base.model_dump(), token=token)


@router.get("/api/devices", response_model=list[DeviceResponse])
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Device).where(Device.user_id == user.id).order_by(Device.created_at.desc())))


@router.post("/api/commands", response_model=CommandResponse, status_code=status.HTTP_201_CREATED)
def create_command(payload: CommandCreate, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.kind not in ALLOWED_COMMANDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Command is not allowed")
    device = db.scalar(select(Device).where(Device.id == payload.device_id, Device.user_id == user.id))
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    requires = payload.kind in CONFIRMATION_REQUIRED
    command = Command(user_id=user.id, device_id=device.id, kind=payload.kind, payload_json=json.dumps(payload.payload), requires_confirmation=requires, status="awaiting_confirmation" if requires else "queued")
    db.add(command)
    db.commit()
    db.refresh(command)
    return _command_response(command)


@router.get("/api/commands", response_model=list[CommandResponse])
def list_commands(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_command_response(c) for c in db.scalars(select(Command).where(Command.user_id == user.id).order_by(Command.created_at.desc()))]


@router.post("/api/commands/{command_id}/approve", response_model=CommandResponse)
def approve_command(command_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    command = db.scalar(select(Command).where(Command.id == command_id, Command.user_id == user.id))
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")
    if command.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Command is not awaiting confirmation")
    command.status = "queued"
    db.commit(); db.refresh(command)
    return _command_response(command)


@router.post("/api/device/commands/{command_id}/result", response_model=CommandResponse)
def complete_command(command_id: str, payload: CommandResult, x_device_token: str = Header(...), db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.token_hash == _digest(x_device_token)))
    if device is None:
        raise HTTPException(status_code=401, detail="Invalid device token")
    command = db.scalar(select(Command).where(Command.id == command_id, Command.device_id == device.id))
    if command is None:
        raise HTTPException(status_code=404, detail="Command not found")
    command.status = "completed" if payload.ok else "failed"
    command.result_json = payload.model_dump_json()
    command.completed_at = datetime.now(timezone.utc)
    device.last_seen_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(command)
    _ingest_device(device, db)
    return _command_response(command)


@router.get("/api/device/commands/next", response_model=Optional[CommandResponse])
def next_command(x_device_token: str = Header(...), db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.token_hash == _digest(x_device_token)))
    if device is None:
        raise HTTPException(status_code=401, detail="Invalid device token")
    device.last_seen_at = datetime.now(timezone.utc)
    command = db.scalar(
        select(Command).where(Command.device_id == device.id, Command.status == "queued").order_by(Command.created_at.asc())
    )
    if command is None:
        db.commit()
        _ingest_device(device, db)
        return None
    command.status = "dispatched"
    db.commit(); db.refresh(command)
    _ingest_device(device, db)
    return _command_response(command)
