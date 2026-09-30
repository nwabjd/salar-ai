"""Amazon Selling Partner API (SP-API) client for SALAR's marketplace tools.

SALAR talks to a self-authorized private SP-API application on the seller's
behalf. Every request goes through three steps:

  1. LWA       — exchange the long-lived refresh token for a short-lived access
                 token (POST .../auth/o2/token).
  2. STS       — assume the SP-API IAM role to get temporary AWS credentials.
  3. SigV4     — sign each Selling Partner request (service ``execute-api``)
                 with those temporary credentials.

The seller account is identified by the marketplace region (NA/EU/FE) and one
or more marketplace IDs. Middle-East marketplaces (Amazon.ae / Amazon.sa) live
in the EU region. See REGIONS for the exact hosts.

Only the seller's own data is read/written (orders, sales metrics, FBA
inventory, listings). No buyer PII is requested, so no Restricted Data Token is
needed. Setup checklist: docs/marketplace/amazon-seller-guide.md.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import logging
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_HEADER_BYTES = 500
_MAX_AMOUNT_ROWS = 120  # order-metrics rows / inventory rows / orders to return

REGIONS = {
    "NA": {
        "lwa_token_url": "https://api.amazon.com/auth/o2/token",
        "sp_host": "sellingpartnerapi-na.amazon.com",
        "aws_region": "us-east-1",
        "sts_host": "sts.amazonaws.com",
    },
    "EU": {
        "lwa_token_url": "https://api.amazon.eu/auth/o2/token",
        "sp_host": "sellingpartnerapi-eu.amazon.com",
        "aws_region": "eu-west-1",
        "sts_host": "sts.eu-west-1.amazonaws.com",
    },
    "FE": {
        "lwa_token_url": "https://api.amazon.co.jp/auth/o2/token",
        "sp_host": "sellingpartnerapi-fe.amazon.com",
        "aws_region": "us-west-2",
        "sts_host": "sts.ap-northeast-1.amazonaws.com",
    },
}

DEFAULT_MARKETPLACE_IDS = "A2VIGQ35RCS4UG,A17E79C6D8DWNP"  # AE, SA


class AmazonSPError(Exception):
    """Normalized Amazon SP-API error. ``.kind`` drives tool messages."""

    def __init__(self, message: str, kind: str = "upstream", status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind  # invalid_config|auth|not_found|timeout|upstream
        self.status = status


def _quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="-_~.")


def _now_iso(days_ago: int = 0) -> str:
    if days_ago:
        ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    else:
        ts = datetime.datetime.now(datetime.timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


def _sigv4_sign(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: bytes,
    *,
    region: str,
    service: str,
    access_key: str,
    secret_key: str,
    session_token: Optional[str] = None,
    amzdate: Optional[str] = None,
) -> Dict[str, str]:
    """AWS Signature Version 4. Returns the headers to send (with Authorization)."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc
    canonical_uri = parsed.path or "/"
    query_pairs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    canonical_query = "&".join(
        f"{_quote(k)}={_quote(v)}"
        for k in sorted(query_pairs)
        for v in sorted(query_pairs[k])
    )

    if amzdate is None:
        amzdate = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    datestamp = amzdate[:8]
    payload_hash = hashlib.sha256(body or b"").hexdigest()

    header_map = {k.lower(): str(v).strip() for k, v in (headers or {}).items()}
    header_map["host"] = host
    header_map["x-amz-date"] = amzdate
    header_map["x-amz-content-sha256"] = payload_hash
    if session_token:
        header_map["x-amz-security-token"] = session_token

    signed_names = sorted(header_map)
    canonical_headers = "".join(f"{name}:{header_map[name]}\n" for name in signed_names)
    signed_headers = ";".join(signed_names)

    canonical_request = "\n".join(
        [method.upper(), canonical_uri, canonical_query, canonical_headers, signed_headers, payload_hash]
    )
    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            amzdate,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), datestamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, service)
    k_signing = _hmac(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    signed_headers_out = {k: header_map[k] for k in signed_names}
    signed_headers_out["Authorization"] = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return signed_headers_out


class AmazonClient:
    """Async Amazon SP-API client (private / self-authorized application)."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        iam_access_key: str,
        iam_secret_key: str,
        role_arn: str,
        region: str = "EU",
        marketplace_ids: Optional[str] = None,
        seller_id: Optional[str] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not (client_id and client_secret and refresh_token and iam_access_key and iam_secret_key and role_arn):
            raise AmazonSPError(
                "Amazon SP-API credentials are incomplete (need LWA client id/secret, refresh "
                "token, IAM keys and the SP-API role ARN). See docs/marketplace/amazon-seller-guide.md.",
                kind="invalid_config",
            )
        region = (region or "EU").strip().upper()
        if region not in REGIONS:
            raise AmazonSPError(
                f"Unknown Amazon region '{region}' (use NA, EU or FE)", kind="invalid_config"
            )
        self._region_cfg = REGIONS[region]
        self._region = region
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._iam_access_key = iam_access_key
        self._iam_secret_key = iam_secret_key
        self._role_arn = role_arn
        self._marketplace_ids = [
            m.strip() for m in (marketplace_ids or DEFAULT_MARKETPLACE_IDS).split(",") if m.strip()
        ] or ["A2VIGQ35RCS4UG"]
        self._seller_id = seller_id or None
        self._client = httpx.AsyncClient(
            timeout=_DEFAULT_TIMEOUT,
            transport=transport,
            headers={"User-Agent": "SALAR/1.0 (marketplace-salar)"},
        )
        # cached auth
        self._access_token: Optional[str] = None
        self._access_token_exp: float = 0.0
        self._session: Optional[Dict[str, str]] = None
        self._session_exp: float = 0.0

    # ------------------------------------------------------------- lifecycle
    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ auth
    async def _fetch_lwa_token(self) -> tuple[str, int]:
        """POST the refresh token to LWA; return (access_token, expires_in)."""
        try:
            r = await self._client.post(
                self._region_cfg["lwa_token_url"],
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        except httpx.HTTPError as exc:
            raise AmazonSPError(f"Could not reach Amazon LWA: {exc}", kind="upstream") from exc
        if r.status_code in (401, 403):
            raise AmazonSPError(
                "Amazon LWA rejected the refresh token / client credentials. Re-run the "
                "self-authorization steps in the setup guide.",
                kind="auth",
                status=r.status_code,
            )
        if r.status_code >= 400:
            raise AmazonSPError(
                f"Amazon LWA returned HTTP {r.status_code}: {r.text[:_MAX_HEADER_BYTES]}", kind="upstream", status=r.status_code
            )
        data = r.json()
        token = data.get("access_token") or data.get("accessToken")
        if not token:
            raise AmazonSPError("Amazon LWA returned no access token", kind="auth")
        return token, int(data.get("expires_in") or 3600)

    async def _sts_assume_role(self) -> tuple[Dict[str, str], float]:
        """Assume the SP-API role; return (session creds, expiry epoch)."""
        body = urllib.parse.urlencode(
            {
                "Action": "AssumeRole",
                "Version": "2011-06-15",
                "RoleArn": self._role_arn,
                "RoleSessionName": "salar-spapi",
                "DurationSeconds": "3600",
            }
        )
        url = f"https://{self._region_cfg['sts_host']}/"
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
        signed = _sigv4_sign(
            "POST",
            url,
            headers,
            body.encode("utf-8"),
            region=self._region_cfg["aws_region"],
            service="sts",
            access_key=self._iam_access_key,
            secret_key=self._iam_secret_key,
        )
        try:
            r = await self._client.post(
                url,
                content=body.encode("utf-8"),
                headers={k: v for k, v in signed.items() if k != "host"},
            )
        except httpx.HTTPError as exc:
            raise AmazonSPError(f"Could not reach AWS STS: {exc}", kind="upstream") from exc
        if r.status_code >= 400:
            raise AmazonSPError(
                f"STS AssumeRole failed (HTTP {r.status_code}): {r.text[:_MAX_HEADER_BYTES]}",
                kind="auth" if r.status_code in (401, 403) else "upstream",
                status=r.status_code,
            )
        ns = {"s": "https://sts.amazonaws.com/doc/2011-06-15/"}
        try:
            root = ET.fromstring(r.text)
            creds = root.find(".//s:Credentials", ns)
            if creds is None:
                raise ValueError("no Credentials element")
            access = creds.findtext("s:AccessKeyId", namespaces=ns)
            secret = creds.findtext("s:SecretAccessKey", namespaces=ns)
            token = creds.findtext("s:SessionToken", namespaces=ns)
            expiry = creds.findtext("s:Expiration", namespaces=ns) or ""
            if not (access and secret and token):
                raise ValueError("incomplete credentials")
        except Exception as exc:
            raise AmazonSPError(
                f"Could not parse the STS AssumeRole response: {exc}", kind="upstream"
            ) from exc
        expiry_epoch = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).timestamp()
        try:
            expiry_epoch = datetime.datetime.fromisoformat(
                expiry.replace("Z", "+00:00").replace("+0000", "+00:00")
            ).timestamp()
        except ValueError:
            pass
        return (
            {
                "access_key_id": access,
                "secret_access_key": secret,
                "session_token": token,
            },
            expiry_epoch,
        )

    async def _ensure_auth(self) -> None:
        import time

        now = time.time()
        if self._access_token and self._access_token_exp > now + 60 and self._session and self._session_exp > now + 60:
            return
        if not self._access_token or self._access_token_exp <= now + 60:
            token, expires_in = await self._fetch_lwa_token()
            self._access_token = token
            self._access_token_exp = now + max(int(expires_in) - 60, 300)
        if not self._session or self._session_exp <= now + 60:
            session, expiry = await self._sts_assume_role()
            self._session = session
            self._session_exp = expiry - 300 if expiry else now + 3300

    # -------------------------------------------------------------- requests
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        await self._ensure_auth()
        host = self._region_cfg["sp_host"]
        url = f"https://{host}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        body = b""
        headers: Dict[str, str] = {}
        if json_body is not None:
            import json as _json

            body = _json.dumps(json_body, default=str).encode("utf-8")
            headers["Content-Type"] = "application/json"
        headers["x-amz-access-token"] = self._access_token or ""
        signed = _sigv4_sign(
            method,
            url,
            headers,
            body,
            region=self._region_cfg["aws_region"],
            service="execute-api",
            access_key=self._session["access_key_id"],
            secret_key=self._session["secret_access_key"],
            session_token=self._session["session_token"],
        )
        try:
            r = await self._client.request(
                method,
                url,
                content=body if body else None,
                headers={k: v for k, v in signed.items() if k != "host"},
            )
        except httpx.TimeoutException as exc:
            raise AmazonSPError(f"Timed out talking to Amazon SP-API: {exc}", kind="timeout") from exc
        except httpx.HTTPError as exc:
            raise AmazonSPError(f"Could not reach Amazon SP-API: {exc}", kind="upstream") from exc
        try:
            payload = r.json()
        except Exception:
            payload = {}
        if r.status_code in (401, 403):
            raise AmazonSPError(
                "Amazon SP-API rejected the request (HTTP %s). Check region, marketplace IDs and "
                "that the app is self-authorized." % r.status_code,
                kind="auth",
                status=r.status_code,
            )
        if r.status_code == 404:
            raise AmazonSPError(
                f"Amazon SP-API resource not found (HTTP 404) for {method} {path}", kind="not_found", status=r.status_code
            )
        if r.status_code >= 400:
            import json as _json

            detail = _json.dumps(payload, default=str)[:_MAX_HEADER_BYTES] if payload else r.text[:_MAX_HEADER_BYTES]
            raise AmazonSPError(
                f"Amazon SP-API returned HTTP {r.status_code}: {detail}", kind="upstream", status=r.status_code
            )
        return payload

    # ---------------------------------------------------------------- sellers
    async def get_seller_info(self) -> Dict[str, Any]:
        """Marketplaces the seller participates in + the merchant sellerId."""
        payload = await self._request("GET", "/sellers/v1/marketplaceParticipations")
        parts = payload.get("payload") or []
        marketplaces = []
        seller_id = self._seller_id
        for p in parts:
            if not seller_id and p.get("sellerId"):
                seller_id = p["sellerId"]
            participation = p.get("participation") or {}
            marketplaces.append(
                {
                    "marketplace_id": p.get("marketplaceId"),
                    "participating": bool(participation.get("isParticipating")),
                    "suspended": bool(participation.get("hasSuspendedListings")),
                }
            )
        if seller_id:
            self._seller_id = seller_id
        return {
            "seller_id": seller_id,
            "marketplace_count": len(marketplaces),
            "marketplaces": marketplaces[: _MAX_AMOUNT_ROWS],
        }

    async def _ensure_seller_id(self) -> str:
        if self._seller_id:
            return self._seller_id
        info = await self.get_seller_info()
        if not info["seller_id"]:
            raise AmazonSPError(
                "Could not determine the sellerId from the SP-API. Check the app's IAM role / "
                "role ARN permissions.",
                kind="auth",
            )
        return info["seller_id"]

    # ------------------------------------------------------------------ sales
    async def get_order_metrics(
        self, days: int = 30, marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Per-day order metrics (orders, sales, units) for the seller."""
        days = max(1, min(int(days or 30), 90))
        mids = marketplace_ids or self._marketplace_ids
        end = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        start = end - datetime.timedelta(days=days - 1)
        interval = f"{start.isoformat().replace('+00:00', 'Z')}--{end.isoformat().replace('+00:00', 'Z')}"
        payload = await self._request(
            "GET",
            "/sales/v1/orderMetrics",
            params={
                "marketplaceIds": ",".join(mids),
                "interval": interval,
                "granularity": "Day",
            },
        )
        rows = payload.get("payload") or []
        daily = []
        totals = {"sales": 0.0, "orders": 0, "units": 0}
        seen_currency = None
        for row in rows[:_MAX_AMOUNT_ROWS]:
            sales = row.get("sales") or {}
            amount = sales.get("totalAmount") or 0
            currency = sales.get("currencyCode") or seen_currency
            if currency and not seen_currency:
                seen_currency = currency
            orders_n = int(row.get("orderCount") or 0)
            units = int(row.get("unitCount") or 0)
            totals["sales"] += float(amount or 0)
            totals["orders"] += orders_n
            totals["units"] += units
            daily.append(
                {
                    "date": (row.get("interval") or "").split("--")[0][:10],
                    "sales": amount,
                    "currency": currency,
                    "orders": orders_n,
                    "units": units,
                }
            )
        return {
            "currency": seen_currency,
            "days": len(daily),
            "interval": interval,
            "totals": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in totals.items()},
            "daily": daily,
        }

    async def list_recent_orders(
        self, days: int = 7, max_orders: int = 20, marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Recent orders (no buyer PII)."""
        days = max(1, min(int(days or 7), 90))
        max_orders = max(1, min(int(max_orders or 20), 100))
        mids = marketplace_ids or self._marketplace_ids
        payload = await self._request(
            "GET",
            "/orders/v0/orders",
            params={
                "MarketplaceIds": ",".join(mids),
                "CreatedAfter": _now_iso(days),
                "MaxResultsPerPage": str(max_orders),
            },
        )
        orders = (payload.get("payload") or {}).get("Orders") or []
        out = []
        for o in orders[:max_orders]:
            total = o.get("OrderTotal") or {}
            out.append(
                {
                    "order_id": o.get("AmazonOrderId"),
                    "purchase_date": o.get("PurchaseDate"),
                    "status": o.get("OrderStatus"),
                    "channel": o.get("FulfillmentChannel"),
                    "items_unshipped": o.get("NumberOfItemsUnshipped"),
                    "total": total.get("Amount"),
                    "currency": total.get("CurrencyCode"),
                }
            )
        return {"count": len(out), "days": days, "orders": out}

    # -------------------------------------------------------------- inventory
    async def get_inventory(self, marketplace_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """FBA inventory summaries (seller SKU, ASIN, available quantity)."""
        mids = marketplace_ids or self._marketplace_ids
        payload = await self._request(
            "GET",
            "/fba/inventory/v1/summaries",
            params={
                "marketplaces": ",".join(mids),
                "granularityType": "Marketplace",
                "details": "false",
                "pageSize": str(min(_MAX_AMOUNT_ROWS, 100)),
            },
        )
        summaries = (payload.get("payload") or {}).get("inventorySummaries") or []
        items = []
        for s in summaries[:_MAX_AMOUNT_ROWS]:
            qty = int(s.get("totalQuantity") or 0)
            items.append(
                {
                    "sku": s.get("sellerSku"),
                    "asin": s.get("asin"),
                    "fn_sku": s.get("fnSku"),
                    "quantity": qty,
                }
            )
        out_of_stock = [i["sku"] for i in items if i["quantity"] == 0]
        return {"count": len(items), "out_of_stock": out_of_stock, "items": items}

    # --------------------------------------------------------------- listings
    async def get_listing(
        self, seller_sku: str, marketplace_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Read one of the seller's listings (price + quantity + status)."""
        if not seller_sku:
            raise AmazonSPError("seller_sku is required", kind="invalid_config")
        seller_id = await self._ensure_seller_id()
        mids = marketplace_ids or self._marketplace_ids
        safe_sku = _quote(seller_sku)
        payload = await self._request(
            "GET",
            f"/listings/2021-08-01/items/{seller_id}/{safe_sku}",
            params={"marketplaceIds": ",".join(mids), "includeSellingRestrictions": "false"},
        )
        attrs = payload.get("attributes") or {}
        prices = attrs.get("standard_price") or [{}]
        availability = attrs.get("fulfillment_availability") or [None]
        first_avail = availability[0] if isinstance(availability, list) and availability else None
        return {
            "sku": payload.get("sku"),
            "product_type": payload.get("productType"),
            "status": payload.get("status"),
            "price": prices[0].get("value") if prices else None,
            "currency": prices[0].get("currency") if prices else None,
            "quantity": first_avail.get("quantity") if isinstance(first_avail, dict) else None,
        }

    async def _update_listing(
        self,
        seller_sku: str,
        patch_operations: List[Dict[str, Any]],
        product_type: Optional[str] = None,
        marketplace_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        seller_id = await self._ensure_seller_id()
        mids = marketplace_ids or self._marketplace_ids
        if not product_type:
            existing = await self.get_listing(seller_sku, mids)
            product_type = existing.get("product_type")
            if not product_type:
                raise AmazonSPError(
                    f"Could not determine the product type for SKU '{seller_sku}' — it may not "
                    "exist as a listing yet.",
                    kind="not_found",
                )
        payload = await self._request(
            "PUT",
            f"/listings/2021-08-01/items/{seller_id}/{_quote(seller_sku)}",
            params={"marketplaceIds": ",".join(mids), "includeSellingRestrictions": "false"},
            json_body={"productType": product_type, "patchOperations": patch_operations},
        )
        issues = payload.get("issues") or []
        return {
            "status": payload.get("status"),
            "sku": payload.get("sku"),
            "issues": [
                {"code": i.get("code"), "severity": i.get("severity"), "message": i.get("message")}
                for i in issues[:_MAX_AMOUNT_ROWS]
            ],
            "note": "Changes are processed asynchronously and can take a few minutes to appear in Seller Central.",
        }

    async def update_price(
        self,
        seller_sku: str,
        price: float,
        currency: str = "AED",
        marketplace_id: Optional[str] = None,
        product_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set the selling price for a SKU (Listings Items API patch)."""
        mid = marketplace_id or (self._marketplace_ids[0] if self._marketplace_ids else "A2VIGQ35RCS4UG")
        ops = [
            {
                "op": "replace",
                "path": "/attributes/standard_price",
                "value": [
                    {"value": f"{float(price):.2f}", "currency": (currency or "AED").upper(), "marketplace_id": mid}
                ],
            }
        ]
        return await self._update_listing(seller_sku, ops, product_type=product_type)

    async def update_quantity(
        self, seller_sku: str, quantity: int, product_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the FBM available quantity for a SKU (Listings Items API patch)."""
        qty = max(0, int(quantity))
        ops = [
            {
                "op": "replace",
                "path": "/attributes/fulfillment_availability",
                "value": [{"fulfillment_channel_code": "DEFAULT", "quantity": qty}],
            }
        ]
        return await self._update_listing(seller_sku, ops, product_type=product_type)

    # ----------------------------------------------------------------- health
    async def health(self) -> Dict[str, Any]:
        try:
            info = await self.get_seller_info()
            return {
                "connected": True,
                "platform": "amazon",
                "region": self._region,
                "seller_id": info["seller_id"],
                "marketplace_count": info["marketplace_count"],
            }
        except AmazonSPError as exc:
            return {"connected": False, "platform": "amazon", "error": f"{exc.kind}: {exc}"}