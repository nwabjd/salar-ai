# backend/app/services/multi_device.py
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import Command, Device, PushToken, SyncState, token_id, utcnow

log = logging.getLogger(__name__)

REMOTE_ACTIONS = {"wake", "lock", "sleep", "shutdown", "restart", "screenshot", "clipboard_push", "open_app", "notification"}


class MultiDevice:
    def __init__(self, db) -> None:
        self.db = db

    # ---- sync ----
    def touch(self, user_id: str, device_id: str) -> SyncState:
        device = self.db.get(Device, device_id)
        if device is None or device.user_id != user_id:
            raise ValueError("device not found")
        device.last_seen_at = utcnow()
        pending = self._pending_count(device_id)
        state = self.db.scalar(select(SyncState).where(SyncState.user_id == user_id, SyncState.device_id == device_id))
        if state is None:
            state = SyncState(id=token_id(), user_id=user_id, device_id=device_id, last_synced_at=utcnow(), pending_commands=pending, updated_at=utcnow())
            self.db.add(state)
            self.db.flush()
        else:
            state.last_synced_at = utcnow()
            state.pending_commands = pending
        return state

    def _pending_count(self, device_id: str) -> int:
        return len(self.db.scalars(select(Command).where(Command.device_id == device_id, Command.status.in_(["queued", "awaiting_confirmation"]))).all())

    def pending_for(self, user_id: str, device_id: str) -> List[Dict[str, Any]]:
        device = self.db.get(Device, device_id)
        if device is None or device.user_id != user_id:
            return []
        rows = self.db.scalars(select(Command).where(Command.device_id == device_id, Command.status.in_(["queued", "awaiting_confirmation"])).order_by(Command.created_at)).all()
        return [
            {"id": c.id, "kind": c.kind, "payload": json.loads(c.payload_json or "{}"), "requires_confirmation": c.requires_confirmation, "status": c.status}
            for c in rows
        ]

    def sync_status(self, user_id: str) -> List[Dict[str, Any]]:
        states = self.db.scalars(select(SyncState).where(SyncState.user_id == user_id)).all()
        return [
            {"device_id": s.device_id, "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None, "pending_commands": s.pending_commands}
            for s in states
        ]

    # ---- remote control ----
    def remote(self, user_id: str, device_id: str, action: str, payload: Optional[Dict[str, Any]] = None, *, requires_confirmation: bool = False) -> Dict[str, Any]:
        if action not in REMOTE_ACTIONS:
            return {"status": "error", "detail": f"invalid action: {action}", "valid": sorted(REMOTE_ACTIONS)}
        device = self.db.get(Device, device_id)
        if device is None or device.user_id != user_id:
            return {"status": "error", "detail": "device not found"}
        needs_confirm = requires_confirmation or action in ("shutdown", "restart", "lock")
        cmd = Command(id=token_id(), user_id=user_id, device_id=device_id, kind=f"remote_{action}", payload_json=json.dumps(payload or {}), status="awaiting_confirmation" if needs_confirm else "queued", requires_confirmation=needs_confirm, created_at=utcnow())
        self.db.add(cmd)
        self.db.flush()
        return {"status": "queued", "command_id": cmd.id, "device": device.name, "action": action, "requires_confirmation": needs_confirm}

    def offline_since(self, user_id: str, *, minutes: int = 5) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        rows = self.db.scalars(select(Device).where(Device.user_id == user_id)).all()
        return [
            {"id": d.id, "name": d.name, "platform": d.platform, "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None}
            for d in rows if d.last_seen_at is None or d.last_seen_at < cutoff
        ]

    # ---- push ----
    def register_push(self, user_id: str, token: str, platform: str, *, device_id: Optional[str] = None) -> PushToken:
        existing = self.db.scalar(select(PushToken).where(PushToken.user_id == user_id, PushToken.token == token))
        if existing:
            existing.platform = platform
            existing.device_id = device_id
            return existing
        pt = PushToken(id=token_id(), user_id=user_id, device_id=device_id, platform=platform, token=token, created_at=utcnow(), updated_at=utcnow())
        self.db.add(pt)
        self.db.flush()
        return pt

    def list_push_tokens(self, user_id: str) -> List[Dict[str, Any]]:
        rows = self.db.scalars(select(PushToken).where(PushToken.user_id == user_id)).all()
        return [{"id": r.id, "platform": r.platform, "token": r.token, "device_id": r.device_id} for r in rows]

    def unregister_push(self, user_id: str, token_id: str) -> bool:
        row = self.db.get(PushToken, token_id)
        if row is None or row.user_id != user_id:
            return False
        self.db.delete(row)
        return True

    # ---- messaging bridge ----
    async def send_via(self, user_id: str, channel: str, to: str, text: str) -> Dict[str, Any]:
        """Unified send across channels. Currently supports whatsapp; others return unavailable."""
        if channel == "whatsapp":
            from .whatsapp import WhatsAppClient
            client = WhatsAppClient()
            try:
                result = await client.send_message(to=to, text=text, user_id=user_id)
                return {"status": "ok", "channel": "whatsapp", "result": result}
            finally:
                await client.close()
        return {"status": "unavailable", "channel": channel, "detail": "channel not configured"}
