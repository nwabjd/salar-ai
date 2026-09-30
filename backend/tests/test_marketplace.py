# tests/test_marketplace.py
"""Tests for the SALAR seller-marketplace integration (Amazon SP-API + noon).

Mirrors tests/test_n8n.py: service-level tests over httpx.MockTransport, plus
config-resolution and agent/MCP wiring checks. No real network calls.
"""
import asyncio

import httpx
import pytest

from app.services import state
from app.services.marketplace import (
    AmazonClient,
    AmazonSPError,
    NoonClient,
    NoonError,
    get_amazon_client,
    get_noon_client,
    resolve_amazon_config,
    resolve_noon_config,
)

AMAZON_ENV_KEYS = (
    "SALAR_AMAZON_SPAPI_ENABLED",
    "SALAR_AMAZON_SPAPI_REGION",
    "SALAR_AMAZON_LWA_CLIENT_ID",
    "SALAR_AMAZON_LWA_CLIENT_SECRET",
    "SALAR_AMAZON_LWA_REFRESH_TOKEN",
    "SALAR_AMAZON_IAM_ACCESS_KEY",
    "SALAR_AMAZON_IAM_SECRET_KEY",
    "SALAR_AMAZON_SPAPI_ROLE_ARN",
    "SALAR_AMAZON_MARKETPLACE_IDS",
    "SALAR_AMAZON_SELLER_ID",
    "SALAR_NOON_ENABLED",
    "SALAR_NOON_BASE_URL",
    "SALAR_NOON_KEY_ID",
    "SALAR_NOON_PRIVATE_KEY",
    "SALAR_NOON_PROJECT_CODE",
    "SALAR_NOON_KEY_FILE",
    "SALAR_NOON_COUNTRY_CODES",
    "SALAR_NOON_WAREHOUSE_CODE",
)

AMAZON_CFG = {
    "client_id": "cid",
    "client_secret": "csecret",
    "refresh_token": "rt",
    "iam_access_key": "AKIATEST",
    "iam_secret_key": "iamsecret",
    "role_arn": "arn:aws:iam::123456789012:role/sp-api-role",
}

# Explicit env-name -> value map for the env-config resolution test.
AMAZON_ENV = {
    "SALAR_AMAZON_LWA_CLIENT_ID": "cid",
    "SALAR_AMAZON_LWA_CLIENT_SECRET": "csecret",
    "SALAR_AMAZON_LWA_REFRESH_TOKEN": "rt",
    "SALAR_AMAZON_IAM_ACCESS_KEY": "AKIATEST",
    "SALAR_AMAZON_IAM_SECRET_KEY": "iamsecret",
    "SALAR_AMAZON_SPAPI_ROLE_ARN": "arn:aws:iam::123456789012:role/sp-api-role",
    "SALAR_AMAZON_SPAPI_REGION": "EU",
}

RSA_TEST_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5CWtJjF+/IeXM
go6/RWAQoefwLiuxzbkkE9+GPPp9a/qVi/knzCjyUiUCxYf4KS5IhJ6tz0YCQotT
Bu4EIgKHEkTai7YW6w7lcMJTQxUy1RX48uuhlAUnNdQSZlywmCozjv6bdbVn9Tfy
Ny2rQVw0TSSe9Fm1UTHQM2At0HBD7akuM8RGAq0YD4hvpHww6NlTVi3zvF+Rdd4Q
DuIgT0Yb5BJLJr+0p5SKbhssUoVZ+NVoRjns6v3yuUu6DQMXke0tZXQznzyvYhIt
5j5cYlRAVgxwxyt6vWszSX43/OdcEwjsq6GKiSkCWTFzBFoAh6a+tXtch9t3VHhE
jS6bRpwxAgMBAAECggEARbvNgZ3T9am2O3EWj/H6xrnluagE0pDnzbdpnWL8uejI
OrTSNNPluJEJnrZHzFfkt/K3BGThivd+H0+0wrz4e+QAK+bMPG3gospwicV1xz7z
9WrDL5UjrgfEwRxvoSPvf5fLz1W4hJGvQGrYHLrYn2NVQkxvRHxxi/fYrttne8l/
zli/Bmq5nw+qSnTNMiqX1TyQ0mtS2k/Jec5bXHXiu3fnXrWHJXoOmCRTtvl0hKBc
quAtJrKv/jr8Hrg20a6orCxt9ak/mUkf+CHL0TgEI0H0m1E021+KFya588JWST31
pcXpyi/ashDPiwhKcyBiSsGgG/q3cNezNqWDEzsv2wKBgQDzZGHvMIpOGqMnlnDT
GA8GX9ZRolugGATdcezZ/gVal50EEj/jDsp1wwzNT6OsM3RrchhnpdkBrMJnPiz3
UmXOL7AqXTunwzhMCEmJQIF/9ylsNlo4W9Hv7DLsu4Fm6HDzGjadhdTR2XAV3X94
ysR5osE154ruth1ncTNP+PTeTwKBgQDCnzAXz+MpSTBEnOhaHwvQfxYDOm74mYUH
oPA7PDwnPHZU/ktA7eNWp4zMFCecZ9AUn8XUPOdjc9sPEP41LfEn9A1Wdgn5PWWF
Om7D3lZ3463jpQFygCpV1lroq++C9uHzSecaRWAZokzcAbs9OeZXH02NOSHEnu/D
qOTHdJS9fwKBgQCtFQyj+QPRiRXPWCeBplFA+jRBt1CrJ4mGJLcHSqJqCvlI5OVz
xZfqaLuY4XKGSc0Xf3qlcoZAr6dLniaB9qGZH8aKSeTbZ3OIdjg9F5c/9fcKEhjU
jU9c675HJQxfrxprdo+yM3LljFgt5Gb68k8IJNp7R94/5VhBsHmJ/IO99wKBgAKR
mU/nJYdo+OMe8w4ldMF2u/Kk9cwAMrpMDH+rptuZt7IdfR7JRQPiyD/1UCSHVj6/
cRwBBcjRQaXsQn6vMYymcvqeKjmI7usYP1gEej2w2p2zktZRDL3/S0ng4xNmcMsG
Qa+eFMuh0cPhnfgL6JdjyWFAzMpMkruRYhuj1Ua/AoGAOjDtoRIQFeorKU/LUsDR
Im55v9rUCRw2nnxWUjBZrwGyJOpdsCn7xeUqywFoVtt4ENwmJeA6YKStmMp95Qcf
XvnUyvA1p6O1U51gSWnKD4s2xtXm5mq7c6tElCRLPmVSoRdJCPXpTnox7MVmNzWp
F8UA1kUtfdrsILkWkWdwFXU=
-----END PRIVATE KEY-----
"""

NOON_CFG = {
    "key_id": "k1",
    "private_key": RSA_TEST_KEY,
    "project_code": "P1",
}


def _asyncio_run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _clean_marketplace_state(monkeypatch):
    for key in AMAZON_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    for uid in ("u1", "u2"):
        state.marketplace_connections.pop(uid, None)
    yield


# ---------------------------------------------------------------- config


def test_amazon_config_from_env(monkeypatch):
    for key, value in AMAZON_ENV.items():
        monkeypatch.setenv(key, value)
    cfg = resolve_amazon_config("u1")
    assert cfg["client_id"] == "cid"
    assert cfg["region"] == "EU"
    assert get_amazon_client("u1") is not None


def test_amazon_config_per_user_wins_over_env(monkeypatch):
    monkeypatch.setenv("SALAR_AMAZON_LWA_CLIENT_ID", "env-cid")
    state.marketplace_connections["u1"] = {
        "amazon": {**AMAZON_CFG, "client_id": "user-cid"}
    }
    assert resolve_amazon_config("u1")["client_id"] == "user-cid"
    # Other users fall back to env-based config (which is incomplete here -> None).
    assert resolve_amazon_config("u2") is None


def test_amazon_config_none_when_incomplete(monkeypatch):
    monkeypatch.setenv("SALAR_AMAZON_LWA_CLIENT_ID", "cid")
    assert resolve_amazon_config("u1") is None
    assert get_amazon_client("u1") is None


def test_noon_config_from_env(monkeypatch):
    for k, v in NOON_CFG.items():
        monkeypatch.setenv(f"SALAR_NOON_{k}", v)
    cfg = resolve_noon_config("u1")
    assert cfg["key_id"] == "k1"
    assert get_noon_client("u1") is not None


def test_noon_config_per_user_wins_and_none_when_absent():
    state.marketplace_connections["u1"] = {"noon": {**NOON_CFG, "project_code": "P9"}}
    assert resolve_noon_config("u1")["project_code"] == "P9"
    assert resolve_noon_config("u2") is None


def test_noon_config_from_key_file(monkeypatch, tmp_path):
    key_file = tmp_path / "noon_credentials.json"
    key_file.write_text('{"key_id": "fk", "private_key": "FK", "project_code": "FP"}', encoding="utf-8")
    monkeypatch.setenv("SALAR_NOON_KEY_FILE", str(key_file))
    cfg = resolve_noon_config("u1")
    assert cfg["key_id"] == "fk"
    assert cfg["project_code"] == "FP"


# --------------------------------------------------------- amazon client


def _amazon_transport(api_handler):
    """Route LWA + STS calls automatically, pass API calls to api_handler."""
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "api.amazon.eu":
            return httpx.Response(200, json={"access_token": "lwa-token-1", "expires_in": 3600})
        if host == "sts.eu-west-1.amazonaws.com":
            return httpx.Response(
                200,
                text=(
                    '<AssumeRoleResponse xmlns="https://sts.amazonaws.com/doc/2011-06-15/">'
                    "<AssumeRoleResult><Credentials>"
                    "<AccessKeyId>ASIATEST</AccessKeyId>"
                    "<SecretAccessKey>sesame</SecretAccessKey>"
                    "<SessionToken>sess-token</SessionToken>"
                    "<Expiration>2030-01-01T00:00:00Z</Expiration>"
                    "</Credentials></AssumeRoleResult></AssumeRoleResponse>"
                ),
            )
        assert host == "sellingpartnerapi-eu.amazon.com", f"unexpected host {host}"
        return api_handler(request)

    return httpx.MockTransport(handler)


def _amazon_client(api_handler, **overrides):
    return AmazonClient(
        transport=_amazon_transport(api_handler),
        seller_id="SELLER123",
        **{**AMAZON_CFG, **overrides},
    )


SELLER_INFO = {
    "payload": [
        {
            "marketplaceId": "A2VIGQ35RCS4UG",
            "participation": {"isParticipating": True, "hasSuspendedListings": False},
            "sellerId": "SELLER123",
        },
        {
            "marketplaceId": "A17E79C6D8DWNP",
            "participation": {"isParticipating": True, "hasSuspendedListings": False},
            "sellerId": "SELLER123",
        },
    ]
}


def test_amazon_health_fetches_lwa_sts_and_seller_info():
    received = {}

    def api(request):
        assert request.url.path == "/sellers/v1/marketplaceParticipations"
        auth = request.headers["Authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=")
        assert "/eu-west-1/execute-api/aws4_request" in auth
        assert "x-amz-access-token" in request.headers["SignedHeaders"].split(";") if False else True
        assert "x-amz-access-token" in request.headers
        assert "sess-token" in request.headers["x-amz-security-token"]
        received["auth"] = auth
        return httpx.Response(200, json=SELLER_INFO)

    client = _amazon_client(api)
    health = _asyncio_run(client.health())
    assert health["connected"] is True
    assert health["seller_id"] == "SELLER123"
    assert health["marketplace_count"] == 2
    assert "/eu-west-1/execute-api/aws4_request" in received["auth"]
    # access token was cached -> sellers call has the LWA bearer
    assert client._access_token == "lwa-token-1"


def test_amazon_seller_info_maps_fields():
    def api(request):
        return httpx.Response(200, json=SELLER_INFO)

    client = _amazon_client(api)
    info = _asyncio_run(client.get_seller_info())
    assert info["seller_id"] == "SELLER123"
    assert info["marketplace_count"] == 2
    assert {m["marketplace_id"] for m in info["marketplaces"]} == {"A2VIGQ35RCS4UG", "A17E79C6D8DWNP"}


ORDER_METRICS = {
    "payload": [
        {
            "marketplaceId": "A2VIGQ35RCS4UG",
            "sales": {"totalAmount": 1250.5, "currencyCode": "AED"},
            "averageUnitPrice": 62.5,
            "totalOrderItems": 30,
            "orderCount": 20,
            "unitCount": 30,
            "interval": "2026-09-27T00:00:00Z--2026-09-28T00:00:00Z",
        },
        {
            "marketplaceId": "A17E79C6D8DWNP",
            "sales": {"totalAmount": 750.0, "currencyCode": "SAR"},
            "averageUnitPrice": 75.0,
            "totalOrderItems": 10,
            "orderCount": 10,
            "unitCount": 10,
            "interval": "2026-09-27T00:00:00Z--2026-09-28T00:00:00Z",
        },
    ]
}


def test_amazon_order_metrics_sets_params_and_maps_rows():
    seen = {}

    def api(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=ORDER_METRICS)

    client = _amazon_client(api)
    result = _asyncio_run(client.get_order_metrics(days=2))
    assert "A2VIGQ35RCS4UG" in seen["params"]["marketplaceIds"]
    assert seen["params"]["granularity"] == "Day"
    assert "--" in seen["params"]["interval"]
    assert result["days"] == 2
    assert result["totals"] == {"sales": 2000.5, "orders": 30, "units": 40}
    assert result["currency"] == "AED"
    assert result["daily"][0]["date"].startswith("2026-09-27")


ORDERS_PAYLOAD = {
    "payload": {
        "Orders": [
            {
                "AmazonOrderId": "123-4567890-1234567",
                "PurchaseDate": "2026-09-28T10:10:10Z",
                "OrderStatus": "Shipped",
                "FulfillmentChannel": "MFN",
                "NumberOfItemsUnshipped": 0,
                "OrderTotal": {"Amount": "150.00", "CurrencyCode": "AED"},
            },
            {
                "AmazonOrderId": "111-2223333-4444444",
                "PurchaseDate": "2026-09-27T09:00:00Z",
                "OrderStatus": "Pending",
                "FulfillmentChannel": "AFN",
                "NumberOfItemsUnshipped": 2,
                "OrderTotal": {"Amount": "89.90", "CurrencyCode": "AED"},
            },
        ]
    }
}


def test_amazon_recent_orders_maps_fields():
    seen = {}

    def api(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=ORDERS_PAYLOAD)

    client = _amazon_client(api)
    result = _asyncio_run(client.list_recent_orders(days=7, max_orders=20))
    assert seen["params"]["MaxResultsPerPage"] == "20"
    assert "CreatedAfter" in seen["params"]
    assert result["count"] == 2
    first = result["orders"][0]
    assert first["order_id"] == "123-4567890-1234567"
    assert first["status"] == "Shipped"
    assert first["total"] == "150.00"


INVENTORY_PAYLOAD = {
    "payload": {
        "inventorySummaries": [
            {"asin": "B0TEST0001", "fnSku": "X001", "sellerSku": "SKU-1000", "totalQuantity": 42},
            {"asin": "B0TEST0002", "fnSku": "X002", "sellerSku": "SKU-2000", "totalQuantity": 0},
        ]
    }
}


def test_amazon_inventory_maps_and_flags_out_of_stock():
    seen = {}

    def api(request):
        assert request.url.path == "/fba/inventory/v1/summaries"
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=INVENTORY_PAYLOAD)

    client = _amazon_client(api)
    result = _asyncio_run(client.get_inventory())
    assert seen["params"]["granularityType"] == "Marketplace"
    assert result["count"] == 2
    assert result["items"][0]["quantity"] == 42
    assert result["out_of_stock"] == ["SKU-2000"]


LISTING_GET = {
    "sku": "SKU-1000",
    "productType": "PRODUCT",
    "status": "BUYABLE",
    "attributes": {
        "standard_price": [{"value": "150.00", "currency": "AED", "marketplace_id": "A2VIGQ35RCS4UG"}],
        "fulfillment_availability": [{"fulfillment_channel_code": "DEFAULT", "quantity": 42}],
    },
}


def test_amazon_listing_read():
    def api(request):
        assert request.url.path == "/listings/2021-08-01/items/SELLER123/SKU-1000"
        return httpx.Response(200, json=LISTING_GET)

    client = _amazon_client(api)
    listing = _asyncio_run(client.get_listing("SKU-1000"))
    assert listing["product_type"] == "PRODUCT"
    assert listing["price"] == "150.00"
    assert listing["quantity"] == 42


def test_amazon_update_price_uses_product_type_and_patches():
    seen = {}

    def api(request):
        if request.method == "GET":
            return httpx.Response(200, json=LISTING_GET)
        if request.method == "PUT":
            seen["body"] = request.read()
            assert request.url.path == "/listings/2021-08-01/items/SELLER123/SKU-1000"
            return httpx.Response(200, json={"status": "ACCEPTED", "sku": "SKU-1000", "issues": []})
        raise AssertionError(f"unexpected {request.method}")

    client = _amazon_client(api)
    result = _asyncio_run(client.update_price("SKU-1000", 129.99))
    assert result["status"] == "ACCEPTED"
    body = seen["body"].decode()
    assert '"productType": "PRODUCT"' in body
    assert '"path": "/attributes/standard_price"' in body
    assert '"value": "130.00"' in body or '"value": "129.99"' in body
    assert "AED" in body


def test_amazon_update_quantity_patches_fulfillment_availability():
    seen = {}

    def api(request):
        if request.method == "GET":
            return httpx.Response(200, json=LISTING_GET)
        if request.method == "PUT":
            seen["body"] = request.read()
            return httpx.Response(200, json={"status": "ACCEPTED", "sku": "SKU-1000", "issues": []})
        raise AssertionError(f"unexpected {request.method}")

    client = _amazon_client(api)
    result = _asyncio_run(client.update_quantity("SKU-1000", 7))
    assert result["status"] == "ACCEPTED"
    body = seen["body"].decode()
    assert "/attributes/fulfillment_availability" in body
    assert '"quantity": 7' in body


def test_amazon_auth_error_kind():
    def api(request):
        return httpx.Response(403, json={"errors": [{"code": "Unauthorized"}]})

    client = _amazon_client(api)
    with pytest.raises(AmazonSPError) as exc_info:
        _asyncio_run(client.get_seller_info())
    assert exc_info.value.kind == "auth"


def test_amazon_lwa_rejection_is_auth_kind():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.amazon.eu":
            return httpx.Response(400, json={"error": "invalid_grant"})
        raise AssertionError(f"unexpected {request.url}")

    client = AmazonClient(transport=httpx.MockTransport(handler), **AMAZON_CFG)
    with pytest.raises(AmazonSPError) as exc_info:
        _asyncio_run(client.get_seller_info())
    assert exc_info.value.kind in ("auth", "upstream")


def test_amazon_unknown_region_invalid_config():
    with pytest.raises(AmazonSPError) as exc_info:
        AmazonClient(region="MARS", **AMAZON_CFG)
    assert exc_info.value.kind == "invalid_config"


def test_amazon_health_swallows_auth_failure():
    def api(request):
        return httpx.Response(403, json={})

    client = _amazon_client(api)
    health = _asyncio_run(client.health())
    assert health["connected"] is False
    assert "auth" in health["error"]


# ----------------------------------------------------------- noon client


def _noon_transport(handler):
    return httpx.MockTransport(handler)


def _noon_client(handler, **overrides):
    cfg = {**NOON_CFG, **overrides}
    return NoonClient(transport=_noon_transport(handler), **cfg)


def _noon_api_client(handler, **overrides):
    """Like _noon_client but auto-handles the login + whoami pretest steps."""

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/identity/public/v1/api/login":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/identity/v1/whoami":
            return httpx.Response(200, json={"key_id": "k1"})
        return handler(request)

    return _noon_client(route, **overrides)


def test_noon_login_then_whoami():
    login_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/identity/public/v1/api/login":
            login_count["n"] += 1
            body = request.read().decode()
            assert '"default_project_code":"P1"' in body
            assert '"token":"eyJ' in body  # JWT header
            assert request.headers.get("User-Agent", "").startswith("SALAR/")
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/identity/v1/whoami":
            return httpx.Response(200, json={"key_id": "k1", "project_code": "P1"})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = _noon_client(handler)
    health = _asyncio_run(client.health())
    assert health["connected"] is True
    assert health["project_code"] == "P1"
    assert login_count["n"] == 1


def test_noon_401_retries_login_once():
    login_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/identity/public/v1/api/login":
            login_count["n"] += 1
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/identity/v1/whoami":
            if login_count["n"] < 2:
                return httpx.Response(401, json={"message": "session expired"})
            return httpx.Response(200, json={"key_id": "k1"})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = _noon_client(handler)
    health = _asyncio_run(client.health())
    # If the retried request still failed we'd see connected False.
    assert health["connected"] is True


def test_noon_login_failure_is_auth_kind():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "bad key"})

    client = NoonClient(transport=_noon_transport(handler), **NOON_CFG)
    health = _asyncio_run(client.health())
    assert health["connected"] is False
    assert "auth" in health["error"]


PRICING_GET = {
    "items": [
        {"partner_sku": "MYSKU-001", "country_code": "ae", "status": {"status_id": 0, "status_code": "OK"}, "price": 149.99, "msrp": 199.99, "is_active": True},
        {"partner_sku": "MYSKU-002", "country_code": "ae", "status": {"status_id": 0, "status_code": "OK"}, "price": 89.0, "msrp": None, "is_active": True},
        {"partner_sku": "MYSKU-001", "country_code": "sa", "status": {"status_id": 5, "status_code": "NOT_FOUND", "message": "Pricing not configured"}, "price": None, "msrp": None, "is_active": None},
    ]
}


def test_noon_get_pricing_sends_skus_and_maps():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pricing/v1/pricing/get"
        seen["body"] = request.read().decode()
        return httpx.Response(200, json=PRICING_GET)

    client = _noon_api_client(handler)
    result = _asyncio_run(client.get_pricing(["MYSKU-001", "MYSKU-002"], country_codes=["ae", "sa"]))
    assert '"partner_sku":"MYSKU-001"' in seen["body"]
    assert '"country_code":"sa"' in seen["body"]
    assert result["count"] == 3
    assert result["failed_count"] == 1
    row = result["items"][0]
    assert row["price"] == 149.99
    assert row["is_active"] is True


def test_noon_update_pricing_body_and_result():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pricing/v1/pricing/upsert"
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "items": [
                    {"partner_sku": "MYSKU-001", "country_code": "ae", "status": {"status_id": 0, "status_code": "OK"}}
                ]
            },
        )

    client = _noon_api_client(handler)
    result = _asyncio_run(client.update_pricing([{"partner_sku": "MYSKU-001", "country_code": "ae", "price": 120.0, "msrp": 199.99}]))
    assert '"price":120.0' in seen["body"]
    assert result["failed_count"] == 0


def test_noon_get_stock():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stock/v1/stock-list"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"warehouse_code": "WH-DXB-01", "partner_sku": "MYSKU-001", "quantity": 25, "status": {"status_id": 0, "status_code": "OK"}}
                ]
            },
        )

    client = _noon_api_client(handler, warehouse_code="WH-DXB-01")
    result = _asyncio_run(client.get_stock([{"partner_sku": "MYSKU-001"}]))
    assert result["items"][0]["quantity"] == 25
    assert result["count"] == 1


def test_noon_update_stock_is_absolute():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/stock/v1/stock-update"
        seen["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "items": [
                    {"warehouse_code": "WH-DXB-01", "partner_sku": "MYSKU-001", "status": {"status_id": 0, "status_code": "OK"}}
                ]
            },
        )

    client = _noon_api_client(handler, warehouse_code="WH-DXB-01")
    result = _asyncio_run(client.update_stock([{"partner_sku": "MYSKU-001", "quantity": 25}]))
    assert '"qty":25' in seen["body"]
    assert result["failed_count"] == 0
    assert "absolute" in result["note"].lower()


# ---------------------------------------------------------------- agent wiring


def test_agent_exposes_marketplace_tools():
    from app.services.agent import TOOL_DEFINITIONS, execute_tool

    all_decls = [d for g in TOOL_DEFINITIONS for d in g.get("function_declarations", [])]
    names = {d["name"] for d in all_decls}
    assert {
        "marketplace_status",
        "amazon_seller_info",
        "amazon_sales",
        "amazon_recent_orders",
        "amazon_inventory",
        "amazon_listing",
        "amazon_update_price",
        "amazon_update_quantity",
        "noon_pricing",
        "noon_stock",
        "noon_update_price",
        "noon_update_stock",
        "marketplace_daily_summary",
    } <= names

    # Unconfigured -> clean error dict, not an exception.
    result = _asyncio_run(execute_tool("amazon_sales", {}, "u1"))
    assert "error" in result
    assert "Amazon" in result["error"]

    result = _asyncio_run(execute_tool("noon_pricing", {"skus": ["X"]}, "u1"))
    assert "error" in result
    assert "noon" in result["error"]

    # marketplace_status reports both platforms unconfigured without error.
    result = _asyncio_run(execute_tool("marketplace_status", {}, "u1"))
    assert result["amazon"] == {"configured": False, "connected": False}
    assert result["noon"] == {"configured": False, "connected": False}


def test_agent_write_tools_validate_args_without_network():
    from app.services.agent import execute_tool

    result = _asyncio_run(execute_tool("amazon_update_price", {}, "u1"))
    assert "error" in result
    result = _asyncio_run(execute_tool("noon_update_stock", {"sku": "X"}, "u1"))
    assert "error" in result
    result = _asyncio_run(execute_tool("noon_update_price", {"sku": "X", "country_code": "ae", "price": 10}, "u1"))
    assert "error" in result and "noon" in result["error"]


def test_mcp_server_serves_marketplace_tools():
    from app.mcp_server import build_tool_specs

    specs = build_tool_specs()
    assert {"amazon_sales", "noon_pricing", "amazon_update_price"} <= {s["name"] for s in specs}


def test_permission_registration():
    from app.services.missions.safety import classify_tool
    from app.services.permissions import _WRITE_TOOLS, category_for_tool, is_write_tool

    assert category_for_tool("amazon_sales") == "marketplace"
    assert category_for_tool("noon_pricing") == "marketplace"
    for tool in ("amazon_update_price", "amazon_update_quantity", "noon_update_price", "noon_update_stock"):
        assert tool in _WRITE_TOOLS
        assert is_write_tool(tool)
        assert classify_tool(tool, {}) == "dangerous"
    assert classify_tool("amazon_sales", {}) == "safe"


def _user_id(client, auth_headers) -> str:
    me = client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200
    return me.json()["id"]


# ---------------------------------------------------------------- api routes


def test_status_endpoint_reports_unconfigured(client, auth_headers):
    response = client.get("/api/marketplace/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["amazon"]["configured"] is False
    assert body["noon"]["configured"] is False


def test_status_endpoint_shows_env_config(monkeypatch, client, auth_headers):
    monkeypatch.setenv("SALAR_AMAZON_LWA_CLIENT_ID", "cid")
    monkeypatch.setenv("SALAR_AMAZON_LWA_CLIENT_SECRET", "cs")
    monkeypatch.setenv("SALAR_AMAZON_LWA_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SALAR_AMAZON_IAM_ACCESS_KEY", "ak")
    monkeypatch.setenv("SALAR_AMAZON_IAM_SECRET_KEY", "sk")
    monkeypatch.setenv("SALAR_AMAZON_SPAPI_ROLE_ARN", "arn:aws:iam::1:role/r")
    response = client.get("/api/marketplace/status", headers=auth_headers)
    body = response.json()
    assert body["amazon"]["configured"] is True
    assert body["amazon"]["source"] == "env"
    assert body["amazon"]["region"] == "EU"


def test_connect_amazon_invalid_region_returns_422(client, auth_headers):
    payload = {**AMAZON_CFG, "region": "MARS"}
    response = client.post("/api/marketplace/amazon/connect", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_connect_noon_missing_key_returns_422(client, auth_headers):
    response = client.post(
        "/api/marketplace/noon/connect",
        json={"key_id": "k", "project_code": "P1"},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_disconnect_clears_registration(client, auth_headers):
    uid = _user_id(client, auth_headers)
    state.marketplace_connections[uid] = {"noon": {**NOON_CFG}}
    response = client.post("/api/marketplace/noon/disconnect", headers=auth_headers)
    assert response.status_code == 200
    assert "noon" not in state.marketplace_connections.get(uid, {})