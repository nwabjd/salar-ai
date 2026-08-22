import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(tags=["auth-relay"])

# In-memory handshake store: the desktop app generates a random code, the
# browser deposits tokens under it, the desktop app collects them once.
# Single-process Render deployment keeps this safe; entries expire quickly.
_LOCK = threading.Lock()
_HANDSHAKES: Dict[str, Dict[str, Any]] = {}
_TTL_SECONDS = 600
_MIN_CODE_LEN = 16


class HandshakePayload(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: Optional[int] = None
    token_type: Optional[str] = "bearer"
    provider_token: Optional[str] = None
    provider_refresh_token: Optional[str] = None


def _purge_expired() -> None:
    now = time.time()
    for code in [c for c, e in _HANDSHAKES.items() if now - e["created_at"] > _TTL_SECONDS]:
        _HANDSHAKES.pop(code, None)


@router.post("/api/auth/handshake/{code}")
def store_handshake(code: str, payload: HandshakePayload):
    if not code or len(code) < _MIN_CODE_LEN:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid handshake code")
    with _LOCK:
        _purge_expired()
        _HANDSHAKES[code] = {"created_at": time.time(), **payload.model_dump(exclude_none=True)}
    return {"status": "stored"}


@router.get("/api/auth/handshake/{code}")
def fetch_handshake(code: str):
    with _LOCK:
        _purge_expired()
        entry = _HANDSHAKES.pop(code, None)
    if entry is None:
        return {"status": "pending"}
    entry.pop("created_at", None)
    return {"status": "ok", "session": entry}
