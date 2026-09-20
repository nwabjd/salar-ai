# backend/tests/test_whatsapp_webhook_secret.py
"""Shared-secret gate for /api/whatsapp/webhook + pass-message ack isolation."""
import json

from app.models import AuditEvent


def _enable_secret(client) -> None:
    client.app.state.settings.whatsapp_webhook_secret = "test-webhook-secret"


def _payload(user_id="any"):
    return {
        "user_id": user_id,
        "from": "123456@s.whatsapp.net",
        "sender_name": "Sender",
        "text": "hello",
        "is_group": False,
        "timestamp": 0,
    }


def test_webhook_requires_secret(client):
    _enable_secret(client)
    resp = client.post("/api/whatsapp/webhook", json=_payload())
    assert resp.status_code == 403


def test_webhook_rejects_wrong_secret(client):
    _enable_secret(client)
    resp = client.post(
        "/api/whatsapp/webhook", headers={"X-WhatsApp-Secret": "wrong"}, json=_payload()
    )
    assert resp.status_code == 403


def test_webhook_forbidden_when_secret_not_configured(client):
    resp = client.post("/api/whatsapp/webhook", json=_payload())
    assert resp.status_code == 403


def test_webhook_accepts_valid_secret(client, exchange):
    _enable_secret(client)
    headers = exchange("wa-owner@example.com")
    me = client.get("/api/auth/me", headers=headers).json()
    resp = client.post(
        "/api/whatsapp/webhook",
        headers={"X-WhatsApp-Secret": "test-webhook-secret"},
        json=_payload(user_id=me["id"]),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_ack_pass_message_scoped_to_owner(client, exchange):
    alice = exchange("alice@example.com")
    bob = exchange("bob@example.com")
    alice_me = client.get("/api/auth/me", headers=alice).json()
    bob_me = client.get("/api/auth/me", headers=bob).json()

    with client.app.state.SessionLocal() as db:
        ev_a = AuditEvent(
            user_id=alice_me["id"],
            action="whatsapp.pass_message",
            detail_json=json.dumps({"message": "for alice", "acknowledged": False}),
        )
        ev_b = AuditEvent(
            user_id=bob_me["id"],
            action="whatsapp.pass_message",
            detail_json=json.dumps({"message": "for bob", "acknowledged": False}),
        )
        db.add_all([ev_a, ev_b])
        db.commit()
        a_id, b_id = ev_a.id, ev_b.id

    # bob cannot acknowledge alice's event
    resp = client.post(f"/api/whatsapp/pass-messages/{a_id}/acknowledge", headers=bob)
    assert resp.status_code == 200
    with client.app.state.SessionLocal() as db:
        assert json.loads(db.get(AuditEvent, a_id).detail_json)["acknowledged"] is False

    # alice can acknowledge her own event
    resp = client.post(f"/api/whatsapp/pass-messages/{a_id}/acknowledge", headers=alice)
    assert resp.status_code == 200
    with client.app.state.SessionLocal() as db:
        assert json.loads(db.get(AuditEvent, a_id).detail_json)["acknowledged"] is True

    # garbage ids never 500
    assert (
        client.post("/api/whatsapp/pass-messages/not-an-int/acknowledge", headers=alice).status_code
        == 200
    )
    assert client.post("/api/whatsapp/pass-messages/---/acknowledge", headers=alice).status_code == 200