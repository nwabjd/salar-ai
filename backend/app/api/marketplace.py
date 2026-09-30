"""Marketplace endpoints — connect, check and disconnect seller accounts.

Supports Amazon (SP-API) and noon (Partner API). Per-user registrations are
stored in-memory (same pattern as n8n / email accounts) and take priority over
the global SALAR_AMAZON_* / SALAR_NOON_* env config. Credentials are never
echoed back by the status endpoint.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user
from ..services.state import marketplace_connections as _marketplace_connections

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


class AmazonConnectConfig(BaseModel):
    client_id: str
    client_secret: str
    refresh_token: str
    iam_access_key: str
    iam_secret_key: str
    role_arn: str
    region: str = "EU"
    marketplace_ids: Optional[str] = None
    seller_id: Optional[str] = None


class NoonConnectConfig(BaseModel):
    base_url: str = "https://noon-api-gateway.noon.partners"
    key_id: str
    private_key: str
    project_code: str
    country_codes: Optional[str] = None
    warehouse_code: Optional[str] = None


def _plain(config: BaseModel) -> Dict[str, str]:
    """Strip whitespace from string fields and drop None values."""
    out: Dict[str, str] = {}
    for k, v in config.model_dump(exclude_none=True).items():
        out[k] = str(v).strip() if isinstance(v, str) else v  # type: ignore[assignment]
    return out


def _store(user_id: str, platform: str, cfg: Dict[str, Any]) -> None:
    _marketplace_connections.setdefault(user_id, {})
    _marketplace_connections[user_id][platform] = cfg


def _drop(user_id: str, platform: str) -> None:
    user_cfg = _marketplace_connections.get(user_id)
    if user_cfg and platform in user_cfg:
        user_cfg.pop(platform, None)


def _platform_status(user_id: str, platform: str) -> Dict[str, Any]:
    """Configured? source? plus non-secret identity info. Never echoes secrets."""
    per_user = (_marketplace_connections.get(user_id) or {}).get(platform)
    if per_user:
        base: Dict[str, Any] = {"configured": True, "source": "user", "uses_global_config": False}
        if platform == "amazon":
            base["region"] = per_user.get("region") or "EU"
            base["marketplace_ids"] = (per_user.get("marketplace_ids") or "").split(",") or None
        else:
            base["base_url"] = per_user.get("base_url") or "https://noon-api-gateway.noon.partners"
            base["countries"] = [
                c for c in (per_user.get("country_codes") or "").split(",") if c
            ] or ["ae"]
        return base
    try:
        if platform == "amazon":
            from ..services.marketplace import resolve_amazon_config

            cfg = resolve_amazon_config(user_id) or resolve_amazon_config(None)
            if not cfg:
                return {"configured": False}
            return {
                "configured": True,
                "source": "env",
                "uses_global_config": True,
                "region": cfg.get("region") or "EU",
                "marketplace_ids": [m for m in (cfg.get("marketplace_ids") or "").split(",") if m] or None,
            }
        from ..services.marketplace import resolve_noon_config

        cfg = resolve_noon_config(user_id) or resolve_noon_config(None)
        if not cfg:
            return {"configured": False}
        return {
            "configured": True,
            "source": "env",
            "uses_global_config": True,
            "base_url": cfg.get("base_url"),
            "countries": [c for c in (cfg.get("country_codes") or "").split(",") if c] or ["ae"],
        }
    except Exception as exc:  # pragma: no cover - defensive
        log.debug("marketplace status failed for %s: %s", platform, exc)
        return {"configured": False}


# ------------------------------------------------------------------- Amazon
@router.post("/amazon/connect")
async def connect_amazon(config: AmazonConnectConfig, user: User = Depends(get_current_user)):
    cfg = _plain(config)
    try:
        from ..services.marketplace import AmazonClient, AmazonSPError

        client = AmazonClient(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            refresh_token=cfg["refresh_token"],
            iam_access_key=cfg["iam_access_key"],
            iam_secret_key=cfg["iam_secret_key"],
            role_arn=cfg["role_arn"],
            region=cfg.get("region") or "EU",
            marketplace_ids=cfg.get("marketplace_ids"),
            seller_id=cfg.get("seller_id"),
        )
    except AmazonSPError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid Amazon config: {exc}")
    try:
        health = await client.health()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection check failed: {exc}")
    finally:
        await client.close()
    if not health.get("connected"):
        raise HTTPException(status_code=400, detail=f"Connection failed: {health.get('error')}")
    _store(user.id, "amazon", cfg)
    return {
        "status": "connected",
        "platform": "amazon",
        "seller_id": health.get("seller_id"),
        "marketplace_count": health.get("marketplace_count"),
    }


@router.post("/noon/connect")
async def connect_noon(config: NoonConnectConfig, user: User = Depends(get_current_user)):
    cfg = _plain(config)
    try:
        from ..services.marketplace import NoonClient, NoonError

        client = NoonClient(
            base_url=cfg.get("base_url") or "https://noon-api-gateway.noon.partners",
            key_id=cfg["key_id"],
            private_key=cfg["private_key"],
            project_code=cfg["project_code"],
            country_codes=cfg.get("country_codes"),
            warehouse_code=cfg.get("warehouse_code"),
        )
    except NoonError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid noon config: {exc}")
    try:
        health = await client.health()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection check failed: {exc}")
    finally:
        await client.close()
    if not health.get("connected"):
        raise HTTPException(status_code=400, detail=f"Connection failed: {health.get('error')}")
    _store(user.id, "noon", cfg)
    return {
        "status": "connected",
        "platform": "noon",
        "project_code": health.get("project_code"),
        "countries": health.get("countries"),
    }


# ------------------------------------------------------------------- status
@router.get("/status")
def marketplace_status(user: User = Depends(get_current_user)):
    return {
        "amazon": _platform_status(user.id, "amazon"),
        "noon": _platform_status(user.id, "noon"),
    }


# --------------------------------------------------------------- disconnect
@router.post("/amazon/disconnect")
def disconnect_amazon(user: User = Depends(get_current_user)):
    _drop(user.id, "amazon")
    return {"status": "disconnected", "platform": "amazon"}


@router.post("/noon/disconnect")
def disconnect_noon(user: User = Depends(get_current_user)):
    _drop(user.id, "noon")
    return {"status": "disconnected", "platform": "noon"}