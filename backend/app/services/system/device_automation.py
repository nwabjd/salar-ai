# backend/app/services/system/device_automation.py
import json
import logging
from typing import Any, Dict, List

from sqlalchemy import select

from ...models import Command, Device, token_id, utcnow

log = logging.getLogger(__name__)


class DeviceAutomation:
    def __init__(self, db) -> None:
        self.db = db

    def list(self, user_id: str) -> List[Dict[str, Any]]:
        rows = self.db.scalars(select(Device).where(Device.user_id == user_id).order_by(Device.created_at.desc())).all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "platform": d.platform,
                "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]

    def issue(self, user_id: str, device_id: str, kind: str, payload: dict = None, *, requires_confirmation: bool = False) -> Dict[str, Any]:
        device = self.db.get(Device, device_id)
        if device is None or device.user_id != user_id:
            return {"status": "error", "detail": "device not found"}
        cmd = Command(id=token_id(), user_id=user_id, device_id=device_id, kind=kind, payload_json=json.dumps(payload or {}), status="queued", requires_confirmation=requires_confirmation, created_at=utcnow())
        self.db.add(cmd)
        self.db.flush()
        return {"status": "queued", "command_id": cmd.id, "device": device.name, "kind": kind}

    def history(self, user_id: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.scalars(select(Command).where(Command.user_id == user_id).order_by(Command.created_at.desc()).limit(limit)).all()
        return [
            {
                "id": c.id,
                "device_id": c.device_id,
                "kind": c.kind,
                "status": c.status,
                "payload": json.loads(c.payload_json or "{}"),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
