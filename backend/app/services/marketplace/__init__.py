"""Seller marketplace integration for SALAR (Amazon SP-API + noon Partner API).

SALAR reads and manages the seller's accounts on Amazon (Selling Partner API)
and noon (Partner API) over their public REST APIs. Credentials are never
bundled: they live in the environment (SALAR_AMAZON_* / SALAR_NOON_*) or in a
per-user in-memory registration via POST /api/marketplace/*/connect, following
the exact pattern of the n8n integration.

Configuration resolution priority (per platform):
  1. Per-user registration: state.marketplace_connections[user_id][platform]
     = { ...config... } (set via the /api/marketplace endpoints).
  2. Global environment: SALAR_AMAZON_* / SALAR_NOON_* env settings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from .amazon_client import REGIONS, AmazonClient, AmazonSPError
from .noon_client import NoonClient, NoonError

__all__ = [
    "REGIONS",
    "AmazonClient",
    "AmazonSPError",
    "NoonClient",
    "NoonError",
    "MarketplaceError",
    "resolve_amazon_config",
    "resolve_noon_config",
    "get_amazon_client",
    "get_noon_client",
]

log = logging.getLogger(__name__)

# Fields that must all be present before Amazon is considered configured.
_AMAZON_REQUIRED = (
    "client_id",
    "client_secret",
    "refresh_token",
    "iam_access_key",
    "iam_secret_key",
    "role_arn",
)


class MarketplaceError(Exception):
    """Normalized marketplace-integration error (kinds match the platform errors)."""

    def __init__(self, message: str, kind: str = "upstream", status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind  # invalid_config|auth|not_found|timeout|upstream
        self.status = status


def _per_user_config(user_id: Optional[str], platform: str) -> Optional[Dict[str, Any]]:
    if not user_id:
        return None
    try:
        from ..state import marketplace_connections

        user_cfg = marketplace_connections.get(user_id) or {}
        cfg = user_cfg.get(platform) or {}
        return cfg if cfg else None
    except Exception:  # pragma: no cover - defensive
        log.debug("marketplace per-user state unavailable", exc_info=True)
        return None


# --------------------------------------------------------------- Amazon
def resolve_amazon_config(user_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Return an Amazon SP-API config dict, or None when unconfigured."""
    per_user = _per_user_config(user_id, "amazon")
    if per_user:
        return dict(per_user)
    try:
        from ...config import Settings

        settings = Settings()
        cfg = {
            "client_id": (settings.amazon_lwa_client_id or "").strip(),
            "client_secret": (settings.amazon_lwa_client_secret or "").strip(),
            "refresh_token": (settings.amazon_lwa_refresh_token or "").strip(),
            "iam_access_key": (settings.amazon_iam_access_key or "").strip(),
            "iam_secret_key": (settings.amazon_iam_secret_key or "").strip(),
            "role_arn": (settings.amazon_spapi_role_arn or "").strip(),
            "region": (settings.amazon_spapi_region or "EU").strip().upper(),
            "marketplace_ids": (settings.amazon_marketplace_ids or "").strip(),
            "seller_id": (settings.amazon_seller_id or "").strip() or None,
        }
    except Exception:  # pragma: no cover - defensive
        log.debug("amazon env settings unavailable", exc_info=True)
        return None
    if not all(cfg.get(f) for f in _AMAZON_REQUIRED):
        return None
    return cfg


def get_amazon_client(
    user_id: Optional[str] = None, transport: Optional[Any] = None
) -> Optional[AmazonClient]:
    """Build (or return None) a configured Amazon client. ``transport`` is for tests."""
    cfg = resolve_amazon_config(user_id)
    if not cfg:
        return None
    return AmazonClient(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        refresh_token=cfg["refresh_token"],
        iam_access_key=cfg["iam_access_key"],
        iam_secret_key=cfg["iam_secret_key"],
        role_arn=cfg["role_arn"],
        region=cfg.get("region") or "EU",
        marketplace_ids=cfg.get("marketplace_ids"),
        seller_id=cfg.get("seller_id"),
        transport=transport,
    )


# ---------------------------------------------------------------- Noon
def resolve_noon_config(user_id: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Return a noon config dict, or None when unconfigured."""
    per_user = _per_user_config(user_id, "noon")
    if per_user:
        return dict(per_user)
    try:
        from ...config import Settings

        settings = Settings()
        cfg = {
            "base_url": (settings.noon_base_url or "https://noon-api-gateway.noon.partners").strip(),
            "key_id": (settings.noon_key_id or "").strip(),
            "private_key": (settings.noon_private_key or "").strip(),
            "project_code": (settings.noon_project_code or "").strip(),
            "key_file": (settings.noon_key_file or "").strip() or None,
            "country_codes": (settings.noon_country_codes or "ae,sa,eg").strip(),
            "warehouse_code": (settings.noon_warehouse_code or "").strip() or None,
        }
    except Exception:  # pragma: no cover - defensive
        log.debug("noon env settings unavailable", exc_info=True)
        return None
    loaded = _load_noon_key_file(cfg)
    if not loaded and not (cfg["key_id"] and cfg["private_key"] and cfg["project_code"]):
        return None
    if loaded:
        cfg.update(loaded)
    return cfg


def _load_noon_key_file(cfg: Dict[str, str]) -> Dict[str, str]:
    """Read key_id / private_key / project_code from a service-account JSON file."""
    path = cfg.get("key_file")
    if not path:
        return {}
    import json
    from pathlib import Path

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for field in ("key_id", "private_key", "project_code"):
        if data.get(field):
            out[field] = str(data[field])
    return out


def get_noon_client(
    user_id: Optional[str] = None, transport: Optional[Any] = None
) -> Optional[NoonClient]:
    """Build (or return None) a configured noon client. ``transport`` is for tests."""
    cfg = resolve_noon_config(user_id)
    if not cfg:
        return None
    return NoonClient(
        base_url=cfg["base_url"],
        key_id=cfg["key_id"],
        private_key=cfg["private_key"],
        project_code=cfg["project_code"],
        country_codes=cfg.get("country_codes"),
        warehouse_code=cfg.get("warehouse_code"),
        transport=transport,
    )