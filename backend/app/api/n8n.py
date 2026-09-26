"""n8n endpoints — connect, check, and disconnect a per-user n8n instance.

Stores the registration in-memory (same pattern as email accounts); falls back
to the global SALAR_N8N_BASE_URL / SALAR_N8N_API_KEY env config when a user has
not registered their own instance.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..security import get_current_user
from ..models import User
from ..services.state import n8n_connections as _n8n_connections

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/n8n", tags=["n8n"])


class N8nConnectionConfig(BaseModel):
    base_url: str
    api_key: str


def _test_connection(base_url: str, api_key: str) -> Optional[str]:
    """Return None when the instance accepts the key, else a human error."""
    import httpx

    from ..services.n8n_client import _normalize_base

    _, api_base = _normalize_base(base_url)
    try:
        r = httpx.get(
            f"{api_base}/workflows",
            params={"limit": 1},
            headers={"X-N8N-API-KEY": api_key, "Accept": "application/json"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        return f"Could not reach n8n at {api_base}: {exc}"
    if r.status_code in (401, 403):
        return f"n8n rejected the API key (HTTP {r.status_code})."
    if r.status_code >= 400:
        return f"n8n returned HTTP {r.status_code}: {r.text[:200]}"
    return None


@router.post("/connect")
def connect_n8n(config: N8nConnectionConfig, user: User = Depends(get_current_user)):
    base_url = (config.base_url or "").strip()
    api_key = (config.api_key or "").strip()
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="base_url and api_key are required")
    error = _test_connection(base_url, api_key)
    if error:
        raise HTTPException(status_code=400, detail=f"Connection failed: {error}")
    _n8n_connections[user.id] = {"base_url": base_url, "api_key": api_key}
    return {"status": "connected", "base_url": base_url}


@router.get("/status")
def n8n_status(user: User = Depends(get_current_user)):
    cfg = _n8n_connections.get(user.id)
    if cfg:
        return {
            "configured": True,
            "base_url": cfg["base_url"],
            "source": "user",
            "uses_global_config": False,
        }
    from ..services.n8n_client import resolve_n8n_config

    global_cfg = resolve_n8n_config(user.id) or resolve_n8n_config(None)
    if global_cfg:
        return {
            "configured": True,
            "base_url": global_cfg["base_url"],
            "source": "user" if _n8n_connections.get(user.id) else "env",
            "uses_global_config": True,
        }
    return {"configured": False, "base_url": None, "uses_global_config": False}


@router.post("/disconnect")
def disconnect_n8n(user: User = Depends(get_current_user)):
    _n8n_connections.pop(user.id, None)
    return {"status": "disconnected"}