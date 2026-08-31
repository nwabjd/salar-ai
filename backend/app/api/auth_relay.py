import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(tags=["auth-relay"])

# In-memory handshake store: the desktop app generates a random code, the
# browser deposits tokens under it, the desktop app collects them once.
from fastapi.responses import HTMLResponse

@router.get("/auth-relay", response_class=HTMLResponse)
def auth_relay_page():
    return """
<!DOCTYPE html>
<html>
<body>
    <script>
        // Extract tokens from URL hash, post to handshake, close.
        const params = new URLSearchParams(window.location.hash.substring(1));
        const accessToken = params.get('access_token');
        const refreshToken = params.get('refresh_token');
        const handshake = new URLSearchParams(window.location.search).get('handshake');
        
        if (accessToken && refreshToken && handshake) {
            fetch(`/api/auth/handshake/${encodeURIComponent(handshake)}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({access_token: accessToken, refresh_token: refreshToken})
            }).then(() => {
                document.body.innerHTML = '<h1>Sign-in successful. You can close this window.</h1>';
            });
        } else {
            document.body.innerHTML = '<h1>Error: Missing authentication parameters.</h1>';
        }
    </script>
</body>
</html>
"""


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
