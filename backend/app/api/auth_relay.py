import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["auth-relay"])

_LOCK = threading.Lock()
_HANDSHAKES: Dict[str, Dict[str, Any]] = {}
_TTL_SECONDS = 600
_MIN_CODE_LEN = 16


@router.get("/auth-relay", response_class=HTMLResponse)
def auth_relay_page():
    return """<!DOCTYPE html>
<html>
<head><title>SALAR Sign-in</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#07080C;color:#e0e0e0">
<div style="text-align:center;max-width:480px;padding:20px">
    <h2 style="color:#7b7cf6">SALAR</h2>
    <p id="status">Completing sign-in...</p>
    <pre id="debug" style="font-size:11px;color:#666;word-break:break-all;text-align:left;background:#111;padding:10px;border-radius:6px;max-height:200px;overflow:auto"></pre>
</div>
<script>
(function() {
    var hash = window.location.hash.substring(1);
    var search = window.location.search;
    var searchParams = new URLSearchParams(search);
    var hashParams = new URLSearchParams(hash);
    var accessToken = hashParams.get('access_token');
    var refreshToken = hashParams.get('refresh_token');
    var handshake = searchParams.get('handshake');
    var statusEl = document.getElementById('status');
    var debugEl = document.getElementById('debug');

    debugEl.textContent = 'search: ' + search + '\\nhash: ' + hash.substring(0,200) + '\\nhandshake: ' + handshake;

    if (!accessToken || !refreshToken || !handshake) {
        statusEl.textContent = 'Error: Missing authentication parameters';
        statusEl.style.color = '#ff6b6b';
        return;
    }

    statusEl.textContent = 'Relaying tokens to backend...';

    fetch('/api/auth/handshake/' + encodeURIComponent(handshake), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({access_token: accessToken, refresh_token: refreshToken})
    }).then(function(r) {
        debugEl.textContent += '\\nPOST /api/auth/handshake/... -> ' + r.status;
        return r.json();
    }).then(function(d) {
        debugEl.textContent += '\\nResponse: ' + JSON.stringify(d);
        statusEl.textContent = 'Sign-in complete! You can close this window.';
        statusEl.style.color = '#70e5aa';
    }).catch(function(err) {
        statusEl.textContent = 'Relay failed: ' + err.message;
        statusEl.style.color = '#ff6b6b';
    });
})();
</script>
</body>
</html>"""


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
