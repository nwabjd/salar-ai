"""noon Partner API client for SALAR's marketplace tools.

SALAR talks to the noon API platform (https://noon-api-gateway.noon.partners)
using a noon service account:

  1. Build a short-lived RS256 JWT (sub = key_id) from the service-account key.
  2. POST /identity/public/v1/api/login with that JWT + the project code to
     obtain a session cookie (kept by the httpx client for later calls).
  3. Call the domain APIs (Pricing, Stock, Offer, ...) with that cookie.

Every request must include a User-Agent header. Marketplace countries are
lowercase country codes: ae (UAE), sa (KSA), eg (Egypt).

Setup checklist: docs/marketplace/noon-seller-guide.md
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_HEADER_BYTES = 500
_MAX_ITEMS = 200

USER_AGENT = "SALAR/1.0 (marketplace-salar)"


class NoonError(Exception):
    """Normalized noon API error. ``.kind`` drives tool messages."""

    def __init__(self, message: str, kind: str = "upstream", status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind  # invalid_config|auth|not_found|timeout|upstream
        self.status = status


class NoonClient:
    """Async noon Partner API client (service-account cookie auth)."""

    def __init__(
        self,
        *,
        base_url: str = "https://noon-api-gateway.noon.partners",
        key_id: str,
        private_key: str,
        project_code: str,
        country_codes: Optional[str] = None,
        warehouse_code: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not (key_id and private_key and project_code):
            raise NoonError(
                "noon credentials are incomplete (need key_id, private_key and project_code — "
                "the service-account JSON from the noon Developer Portal).",
                kind="invalid_config",
            )
        self._base_url = (base_url or "https://noon-api-gateway.noon.partners").strip().rstrip("/")
        self._key_id = key_id
        self._private_key = private_key
        self._project_code = project_code
        self._country_codes = [
            c.strip().lower() for c in (country_codes or "ae,sa,eg").split(",") if c.strip()
        ] or ["ae"]
        self._warehouse_code = warehouse_code
        self._logged_in = False
        # NOTE: httpx persists the login cookies for the lifetime of this client.
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=_DEFAULT_TIMEOUT,
            transport=transport,
            headers={"User-Agent": USER_AGENT},
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ auth
    def _build_jwt(self) -> str:
        import time
        import uuid

        import jwt

        return jwt.encode(
            {
                "sub": self._key_id,
                "iat": int(time.time()),
                "jti": str(uuid.uuid4()),
            },
            self._private_key,
            algorithm="RS256",
        )

    async def _ensure_login(self) -> None:
        if self._logged_in:
            return
        try:
            r = await self._client.post(
                "/identity/public/v1/api/login",
                json={"token": self._build_jwt(), "default_project_code": self._project_code},
            )
        except httpx.HTTPError as exc:
            raise NoonError(f"Could not reach noon identity service: {exc}", kind="upstream") from exc
        if r.status_code in (401, 403):
            raise NoonError(
                "noon rejected the service-account key (HTTP %s). Check key_id / private_key / "
                "project_code in the setup guide." % r.status_code,
                kind="auth",
                status=r.status_code,
            )
        if r.status_code >= 400:
            raise NoonError(
                f"noon login failed with HTTP {r.status_code}: {r.text[:_MAX_HEADER_BYTES]}",
                kind="upstream",
                status=r.status_code,
            )
        self._logged_in = True

    async def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Any] = None,
        *,
        _retried: bool = False,
    ) -> Dict[str, Any]:
        await self._ensure_login()
        try:
            if json_body is not None:
                r = await self._client.request(method, path, json=json_body)
            else:
                r = await self._client.request(method, path)
        except httpx.TimeoutException as exc:
            raise NoonError(f"Timed out talking to noon API: {exc}", kind="timeout") from exc
        except httpx.HTTPError as exc:
            raise NoonError(f"Could not reach noon API: {exc}", kind="upstream") from exc
        if r.status_code in (401, 403):
            if not _retried:
                self._logged_in = False
                return await self._request(method, path, json_body=json_body, _retried=True)
            raise NoonError(
                "noon rejected the session cookie (HTTP %s). Re-check service-account credentials." % r.status_code,
                kind="auth",
                status=r.status_code,
            )
        if r.status_code == 404:
            raise NoonError(f"noon resource not found (HTTP 404) for {method} {path}", kind="not_found", status=r.status_code)
        if r.status_code >= 400:
            detail = r.text[:_MAX_HEADER_BYTES]
            raise NoonError(
                f"noon returned HTTP {r.status_code}: {detail}", kind="upstream", status=r.status_code
            )
        try:
            return r.json()
        except Exception:
            return {}

    # -------------------------------------------------------------- identity
    async def get_whoami(self) -> Dict[str, Any]:
        return await self._request("GET", "/identity/v1/whoami")

    # ------------------------------------------------------------------ price
    async def get_pricing(
        self, skus: List[str], country_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Current price / MSRP / active flag per SKU + country."""
        skus = [str(s).strip() for s in skus if str(s).strip()][:_MAX_ITEMS]
        if not skus:
            raise NoonError("At least one partner SKU is required", kind="invalid_config")
        countries = [c.lower() for c in (country_codes or self._country_codes)] or ["ae"]
        items = [
            {"partner_sku": sku, "country_code": cc}
            for sku in skus
            for cc in countries
        ]
        payload = await self._request("POST", "/pricing/v1/pricing/get", json_body={"items": items})
        rows = []
        failed = 0
        for item in (payload.get("items") or [])[:_MAX_ITEMS * 4]:
            status = item.get("status") or {}
            code = status.get("status_code") or "OK"
            if code != "OK":
                failed += 1
            rows.append(
                {
                    "sku": item.get("partner_sku"),
                    "country": item.get("country_code"),
                    "price": item.get("price"),
                    "msrp": item.get("msrp"),
                    "is_active": item.get("is_active"),
                    "status": code,
                }
            )
        return {
            "count": len(rows),
            "failed_count": failed,
            "items": rows,
            "countries": countries,
        }

    async def update_pricing(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create/update price + MSRP + active flag for SKUs."""
        normalized = []
        for it in items[:_MAX_ITEMS]:
            sku = str(it.get("partner_sku") or it.get("sku") or "").strip()
            cc = str(it.get("country_code") or "").strip().lower()
            if not sku or not cc:
                continue
            entry: Dict[str, Any] = {"partner_sku": sku, "country_code": cc}
            if it.get("price") is not None:
                entry["price"] = float(it["price"])
            if it.get("msrp") is not None:
                entry["msrp"] = float(it["msrp"])
            if it.get("is_active") is not None:
                entry["is_active"] = bool(it["is_active"])
            normalized.append(entry)
        if not normalized:
            raise NoonError("At least one {partner_sku, country_code, price} item is required", kind="invalid_config")
        payload = await self._request("POST", "/pricing/v1/pricing/upsert", json_body={"items": normalized})
        rows = []
        for item in (payload.get("items") or []):
            status = item.get("status") or {}
            rows.append(
                {
                    "sku": item.get("partner_sku"),
                    "country": item.get("country_code"),
                    "status": status.get("status_code") or "UNKNOWN",
                    "message": status.get("message") or status.get("status_code") or "",
                }
            )
        return {
            "count": len(rows),
            "failed_count": sum(1 for r in rows if r["status"] != "OK"),
            "items": rows,
            "note": "Price changes propagate to noon's marketplaces shortly after confirmation.",
        }

    # ------------------------------------------------------------------ stock
    async def get_stock(self, pairs: List[Dict[str, str]]) -> Dict[str, Any]:
        """Current quantities for (warehouse, partner_sku) pairs."""
        normalized = []
        for p in pairs[:_MAX_ITEMS]:
            sku = str(p.get("partner_sku") or p.get("sku") or "").strip()
            wh = str(p.get("warehouse_code") or self._warehouse_code or "").strip()
            if not sku or not wh:
                continue
            normalized.append({"warehouse_code": wh, "partner_sku": sku})
        if not normalized:
            raise NoonError(
                "At least one (warehouse_code, partner_sku) pair is required — or set "
                "SALAR_NOON_WAREHOUSE_CODE so SALAR can fill it in.",
                kind="invalid_config",
            )
        payload = await self._request("POST", "/stock/v1/stock-list", json_body={"items": normalized})
        items = []
        for item in (payload.get("items") or []):
            status = item.get("status") or {}
            qty = item.get("qty")
            if qty is None:
                qty = item.get("quantity")
            items.append(
                {
                    "warehouse": item.get("warehouse_code"),
                    "sku": item.get("partner_sku"),
                    "quantity": qty,
                    "status": status.get("status_code") or "OK",
                }
            )
        return {"count": len(items), "items": items}

    async def update_stock(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Set absolute available quantity for (warehouse, SKU) pairs.

        The quantity sent is **absolute** — it becomes the new available
        quantity on noon, it is not added to the current value.
        """
        normalized = []
        for it in items[:_MAX_ITEMS]:
            sku = str(it.get("partner_sku") or it.get("sku") or "").strip()
            wh = str(it.get("warehouse_code") or self._warehouse_code or "").strip()
            qty = it.get("quantity", it.get("qty"))
            if not sku or not wh or qty is None:
                continue
            normalized.append({"warehouse_code": wh, "partner_sku": sku, "qty": max(0, int(qty))})
        if not normalized:
            raise NoonError(
                "At least one {partner_sku, quantity} item is required (warehouse_code comes "
                "from the item or SALAR_NOON_WAREHOUSE_CODE).",
                kind="invalid_config",
            )
        payload = await self._request("POST", "/stock/v1/stock-update", json_body={"items": normalized})
        rows = []
        for item in (payload.get("items") or []):
            status = item.get("status") or {}
            rows.append(
                {
                    "sku": item.get("partner_sku"),
                    "warehouse": item.get("warehouse_code"),
                    "status": status.get("status_code") or "UNKNOWN",
                    "message": status.get("message") or status.get("status_code") or "",
                }
            )
        return {
            "count": len(rows),
            "failed_count": sum(1 for r in rows if r["status"] != "OK"),
            "items": rows,
            "note": "Quantities are absolute: noon now offers exactly what you sent until the next update.",
        }

    # ----------------------------------------------------------------- health
    async def health(self) -> Dict[str, Any]:
        try:
            whoami = await self.get_whoami()
            return {
                "connected": True,
                "platform": "noon",
                "base_url": self._base_url,
                "project_code": self._project_code,
                "countries": self._country_codes,
                "whoami_keys": sorted(whoami.keys())[:_MAX_HEADER_BYTES] if isinstance(whoami, dict) else None,
            }
        except NoonError as exc:
            return {"connected": False, "platform": "noon", "error": f"{exc.kind}: {exc}"}