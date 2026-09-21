import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("fake http error", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture()
def paypal_client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'paypal-test.db'}",
        jwt_secret="test-secret-that-is-long-enough-for-sha256",
        bootstrap_email="owner@example.com",
        bootstrap_password="CorrectHorseBatteryStaple!",
        allowed_origins=["https://salar.example.com"],
        storage_dir=tmp_path / "uploads",
        environment="test",
        gemini_api_key="test-gemini-key",
        paypal_client_id="paypal-test-client",
        paypal_secret="paypal-test-secret",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_paypal(monkeypatch):
    calls = []

    token_response = _FakeResponse({"access_token": "access-test-token"})
    order_response = _FakeResponse(
        {
            "id": "ORDER-123",
            "status": "CREATED",
            "links": [
                {"rel": "approve", "href": "https://www.paypal.com/checkout?token=ORDER-123"},
                {"rel": "self", "href": "https://api.paypal.com/v2/checkout/orders/ORDER-123"},
            ],
        }
    )

    def fake_post(url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        if "oauth2/token" in url:
            return token_response
        return order_response

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def test_prices_are_public(client):
    response = client.get("/api/billing/prices")

    assert response.status_code == 200
    body = response.json()
    assert "price_free" in body
    assert "price_pro" in body
    assert "price_team" in body
    assert body["price_pro"]["plan"] == "pro"
    assert body["price_team"]["plan"] == "team"


def test_checkout_unknown_price_returns_404(client):
    response = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_unknown"},
    )

    assert response.status_code == 404


def test_checkout_free_price_creates_wallet_intent(client):
    response = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_free", "chain_id": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "wallet"
    assert "intent_id" in body
    assert "message" in body
    assert "amount" in body


def test_checkout_pro_requires_no_stripe(client):
    response = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "chain_id": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "wallet"
    assert body["amount"] == "1200"
    assert body["currency"] == "USDC"


def test_checkout_paypal_not_configured_returns_501(client):
    response = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "paypal": True},
    )

    assert response.status_code == 501


def test_verify_unknown_intent_returns_404(client):
    response = client.post(
        "/api/billing/verify",
        json={
            "intent_id": "nonexistent",
            "address": "0xabc",
            "signature": "0xfake",
        },
    )

    assert response.status_code == 404


def test_status_requires_auth(client):
    response = client.get("/api/billing/status")

    assert response.status_code == 401


def test_status_returns_free_plan_for_new_user(client, exchange):
    headers = exchange("freeuser@example.com")
    response = client.get("/api/billing/status", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["limit"] == 500
    assert body["usage"] == 0
    assert body["exempt"] is False
    assert body["is_admin"] is False
    assert "wallet" in body["payment_methods"]


def test_status_marks_admin_as_exempt(client, admin_headers):
    response = client.get("/api/billing/status", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["exempt"] is True
    assert body["is_admin"] is True
    assert body["plan"] in ("free", "pro", "team")


def test_paypal_checkout_creates_order_when_configured(paypal_client, fake_paypal):
    response = paypal_client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "paypal": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "paypal"
    assert body["approval_url"] == "https://www.paypal.com/checkout?token=ORDER-123"
    assert "intent_id" in body


def test_paypal_checkout_uses_credentials_and_sends_valid_order(paypal_client, fake_paypal):
    paypal_client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "paypal": True, "email": "buyer@example.com"},
    )

    assert len(fake_paypal) == 2
    token_call, order_call = fake_paypal

    assert token_call["url"] == "https://api-m.paypal.com/v1/oauth2/token"
    assert token_call["kwargs"]["data"] == {"grant_type": "client_credentials"}
    assert token_call["kwargs"]["auth"] == ("paypal-test-client", "paypal-test-secret")

    assert order_call["url"] == "https://api.paypal.com/v2/checkout/orders"
    assert order_call["kwargs"]["headers"]["Authorization"] == "Bearer access-test-token"
    order_body = order_call["kwargs"]["json"]
    assert order_body["intent"] == "CAPTURE"
    assert order_body["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "12"}
    assert order_body["purchase_units"][0]["payer"] == {"email_address": "buyer@example.com"}
    assert order_body["application_context"]["return_url"] == "https://salaar.cloud/?checkout=success"
    assert order_body["application_context"]["cancel_url"] == "https://salaar.cloud/#pricing"


def test_paypal_capture_after_order_created(paypal_client, fake_paypal):
    created = paypal_client.post(
        "/api/billing/checkout",
        json={"price_id": "price_team", "paypal": True},
    ).json()
    intent_id = created["intent_id"]

    response = paypal_client.post(f"/api/billing/capture/{intent_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["intent_id"] == intent_id
    assert body["plan"] == "team"
    assert body["capturable"] is True


def test_paypal_capture_unknown_intent_returns_404(paypal_client, fake_paypal):
    response = paypal_client.post("/api/billing/capture/nonexistent")

    assert response.status_code == 404


def test_verify_paypal_intent_is_rejected(paypal_client, fake_paypal):
    created = paypal_client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "paypal": True},
    ).json()

    response = paypal_client.post(
        "/api/billing/verify",
        json={
            "intent_id": created["intent_id"],
            "address": "0xabc",
            "signature": "0xfake",
        },
    )

    assert response.status_code == 400


def test_verify_wallet_signature_upgrades_plan(client, exchange):
    from eth_account import Account
    from eth_account.messages import encode_defunct

    headers = exchange("buyer@example.com")
    acct = Account.create()
    created = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "chain_id": 1},
    ).json()
    signed = Account.sign_message(
        encode_defunct(text=created["message"]),
        private_key=acct.key,
    )
    response = client.post(
        "/api/billing/verify",
        json={
            "intent_id": created["intent_id"],
            "address": acct.address,
            "signature": signed.signature.hex(),
            "email": "buyer@example.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["plan"] == "pro"

    status = client.get("/api/billing/status", headers=headers).json()
    assert status["plan"] == "pro"
    assert status["limit"] == 5000


def test_verify_wallet_signature_rejects_wrong_signer(client):
    from eth_account import Account
    from eth_account.messages import encode_defunct

    signer = Account.create()
    other = Account.create()
    created = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "chain_id": 1},
    ).json()
    signed = Account.sign_message(
        encode_defunct(text=created["message"]),
        private_key=signer.key,
    )
    response = client.post(
        "/api/billing/verify",
        json={
            "intent_id": created["intent_id"],
            "address": other.address,
            "signature": signed.signature.hex(),
        },
    )

    assert response.status_code == 400
