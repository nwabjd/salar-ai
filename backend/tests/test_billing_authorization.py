# backend/tests/test_billing_authorization.py
"""Billing /verify binds plan changes to the authenticated caller."""
from eth_account import Account
from eth_account.messages import encode_defunct


def test_verify_cannot_upgrade_another_account(client, exchange):
    alice = exchange("alice@example.com")
    bob = exchange("bob@example.com")  # exists BEFORE the verify call

    acct = Account.create()
    created = client.post(
        "/api/billing/checkout", json={"price_id": "price_pro", "chain_id": 1}
    ).json()
    signed = Account.sign_message(
        encode_defunct(text=created["message"]), private_key=acct.key
    )

    # alice signs the intent but supplies bob's email in the body
    resp = client.post(
        "/api/billing/verify",
        headers=alice,
        json={
            "intent_id": created["intent_id"],
            "address": acct.address,
            "signature": signed.signature.hex(),
            "email": "bob@example.com",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["plan"] == "pro"

    # the authenticated caller gets upgraded, not the spoofed email
    alice_status = client.get("/api/billing/status", headers=alice).json()
    assert alice_status["plan"] == "pro"
    bob_status = client.get("/api/billing/status", headers=bob).json()
    assert bob_status["plan"] == "free"


def test_verify_guest_email_flow_still_works(client):
    """Unauthenticated (email-only) checkout continuation is preserved."""
    acct = Account.create()
    created = client.post(
        "/api/billing/checkout",
        json={"price_id": "price_pro", "chain_id": 1, "email": "guest@example.com"},
    ).json()
    signed = Account.sign_message(
        encode_defunct(text=created["message"]), private_key=acct.key
    )
    resp = client.post(
        "/api/billing/verify",
        json={
            "intent_id": created["intent_id"],
            "address": acct.address,
            "signature": signed.signature.hex(),
        },
    )
    assert resp.status_code == 200