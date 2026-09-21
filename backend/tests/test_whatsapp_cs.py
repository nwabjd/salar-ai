"""Tests for the WhatsApp Customer Service capability (official Meta Cloud API).

Covers the 14-phase acceptance surface that is testable without live Meta
credentials: webhook verification, signature validation, idempotent ingestion,
delivery-status reconciliation, the AI reply pipeline (fake Gemini), human
handover, knowledge-base retrieval, admin APIs, and security (no secrets in
responses, admin-only access). Live sends are always mocked.
"""
import hashlib
import hmac
import json
import secrets
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models import (
    WhatsAppCSConversation,
    WhatsAppCSCustomer,
    WhatsAppCSKnowledgeEntry,
    WhatsAppCSMessage,
    WhatsAppCSOutbound,
    WhatsAppCSWebhookEvent,
)
from app.services.whatsapp_cs_agent import (
    ESCALATE_MARKER,
    build_messages,
    decide_escalation,
    detect_escalation,
    handover_text,
    normalize_reply,
)
from app.services.whatsapp_cs_cloud import WhatsAppCloudAPIError, WhatsAppCloudClient
from app.services.whatsapp_cs_engine import process_webhook_payload, reply_worker
from app.services.whatsapp_cs_store import WhatsAppCSStore

APP_SECRET = "app-secret-test"
VERIFY_TOKEN = "verify-token-test"


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


class FakeGemini:
    def __init__(self, text=None, error=None):
        self.calls = []
        self.text = text if text is not None else "Our store hours are 9:00–17:00, seven days a week."
        self.error = error

    async def chat_with_tools(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        if self.error is not None:
            raise self.error
        return {"text": self.text, "function_calls": [], "finish_reason": "STOP"}


class FakeCloud:
    def __init__(self, error=None):
        self.error = error
        self.sent = []

    async def send_text(self, to, text, **kwargs):
        if self.error is not None:
            raise self.error
        self.sent.append({"to": to, "text": text})
        return f"wamid.OUT.{len(self.sent)}"


def _configure(client: TestClient) -> None:
    settings = client.app.state.settings
    settings.whatsapp_cs_app_secret = APP_SECRET
    settings.whatsapp_cs_verify_token = VERIFY_TOKEN
    settings.whatsapp_cs_access_token = "access-token-test"
    settings.whatsapp_cs_phone_number_id = "111222333"
    settings.whatsapp_cs_business_account_id = "1020304050"
    settings.whatsapp_cs_enabled = True
    settings.whatsapp_cs_ai_enabled = True


def _sign(payload: bytes, secret: str = APP_SECRET) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _text_payload(wa="15550000001", mid="wamid.IN.0001", body="Hi, what are your hours?"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15551234567", "phone_number_id": "111222333"},
                            "contacts": [{"profile": {"name": "Aisha"}, "wa_id": wa}],
                            "messages": [
                                {"from": wa, "id": mid, "timestamp": "1730000000", "type": "text",
                                 "text": {"body": body}},
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _statuses_payload(mid="wamid.OUT.0001", status="delivered"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {"id": mid, "recipient_id": "15550000001", "status": status, "timestamp": "1730000001"}
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _state(client: TestClient, gemini=None, cloud=None) -> SimpleNamespace:
    return SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        settings=client.app.state.settings,
        coordinator=SimpleNamespace(gemini=gemini or FakeGemini()),
        whatsapp_cs_cloud=cloud or FakeCloud(),
    )


def _seed_incoming(client: TestClient, body="Help with my order", wa="15550000001", mid=None):
    """Persist one incoming message; returns (account_id, conversation_id, message_id)."""
    db = client.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.ensure_account()
        db.flush()
        customer = store.get_or_create_customer(account.id, wa, "Aisha")
        conversation = store.get_or_create_conversation(account.id, customer.id)
        message, created = store.persist_incoming(
            account.id,
            conversation.id,
            external_message_id=mid or f"wamid.IN.{secrets.token_hex(6)}",
            message_type="text",
            body=body,
        )
        db.commit()
        return account.id, conversation.id, message.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _seed_outbound(client: TestClient, *, whatsapp_message_id="wamid.OUT.0001", text="Checking on that for you."):
    db = client.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.ensure_account()
        db.flush()
        customer = store.get_or_create_customer(account.id, "15550000001", "Aisha")
        conversation = store.get_or_create_conversation(account.id, customer.id)
        outbound, message = store.record_outgoing(
            account,
            conversation,
            wa_phone=customer.wa_id,
            text=text,
            idempotency_key=f"seed-{secrets.token_hex(5)}",
        )
        outbound.whatsapp_message_id = whatsapp_message_id
        outbound.status = "sent"
        message.external_message_id = whatsapp_message_id
        message.delivery_status = "sent"
        db.commit()
        return outbound.id, message.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Webhook verification / signature
# ---------------------------------------------------------------------------


def test_webhook_verification_returns_challenge(client):
    _configure(client)
    response = client.get(
        "/api/whatsapp-cs/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "CHALLENGE_123"},
    )
    assert response.status_code == 200
    assert response.text == "CHALLENGE_123"


def test_webhook_verification_wrong_token_rejected(client):
    _configure(client)
    response = client.get(
        "/api/whatsapp-cs/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "CHALLENGE_123"},
    )
    assert response.status_code == 403


def test_webhook_verification_wrong_mode_rejected(client):
    _configure(client)
    response = client.get(
        "/api/whatsapp-cs/webhook",
        params={"hub.mode": "unsubscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "CHALLENGE_123"},
    )
    assert response.status_code == 403


def test_signature_validator_unit():
    payload = b'{"hello": "world"}'
    header = _sign(payload)
    assert WhatsAppCloudClient.validate_signature(payload, header, APP_SECRET) is True
    assert WhatsAppCloudClient.validate_signature(payload, header, "wrong-secret") is False
    assert WhatsAppCloudClient.validate_signature(payload, None, APP_SECRET) is False
    assert WhatsAppCloudClient.validate_signature(payload, "md5=deadbeef", APP_SECRET) is False


def test_webhook_post_not_configured_returns_503(client):
    # No settings configured in this fresh fixture.
    response = client.post("/api/whatsapp-cs/webhook", content=b"{}", headers={"X-Hub-Signature-256": _sign(b"{}")})
    assert response.status_code == 503


def test_webhook_post_missing_signature_rejected(client):
    _configure(client)
    response = client.post("/api/whatsapp-cs/webhook", content=json.dumps(_text_payload()).encode())
    assert response.status_code == 403


def test_webhook_post_bad_signature_rejected(client):
    _configure(client)
    raw = json.dumps(_text_payload()).encode()
    response = client.post(
        "/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw, "other-secret")}
    )
    assert response.status_code == 403


def test_webhook_post_ignores_foreign_object(client):
    _configure(client)
    payload = {"object": "instagram", "entry": []}
    raw = json.dumps(payload).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    assert response.json()["ignored"] == "object"


def test_webhook_post_malformed_json_acknowledged(client):
    _configure(client)
    raw = b"{not-json"
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    assert response.json()["ignored"] == "malformed"


# ---------------------------------------------------------------------------
# Incoming message ingestion + idempotency
# ---------------------------------------------------------------------------


def test_webhook_post_persists_message(client):
    _configure(client)
    raw = json.dumps(_text_payload(body="What are your opening hours?")).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    assert response.json()["new_messages"] == 1

    with client.app.state.SessionLocal() as db:
        customer = db.scalar(select(WhatsAppCSCustomer).where(WhatsAppCSCustomer.wa_id == "15550000001"))
        assert customer is not None and customer.profile_name == "Aisha"
        conversation = db.scalar(select(WhatsAppCSConversation).where(WhatsAppCSConversation.customer_id == customer.id))
        assert conversation is not None and conversation.handling_mode == "ai" and conversation.status == "open"
        message = db.scalar(select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == "wamid.IN.0001"))
        assert message is not None
        assert message.direction == "incoming"
        assert message.message_type == "text"
        assert message.body == "What are your opening hours?"
        events = db.scalar(select(func.count()).select_from(WhatsAppCSWebhookEvent))
        assert events == 1


def test_webhook_post_redelivery_is_idempotent(client):
    _configure(client)
    raw = json.dumps(_text_payload(body="Order status?")).encode()
    headers = {"X-Hub-Signature-256": _sign(raw)}
    first = client.post("/api/whatsapp-cs/webhook", content=raw, headers=headers)
    second = client.post("/api/whatsapp-cs/webhook", content=raw, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["new_messages"] == 1
    assert second.json()["new_messages"] == 0
    with client.app.state.SessionLocal() as db:
        incoming = db.scalar(
            select(func.count()).select_from(WhatsAppCSMessage).where(WhatsAppCSMessage.direction == "incoming")
        )
        assert incoming == 1


def test_webhook_post_media_message(client):
    _configure(client)
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"profile": {"name": "Aisha"}, "wa_id": "15550000001"}],
                            "messages": [
                                {
                                    "from": "15550000001",
                                    "id": "wamid.IN.IMG.1",
                                    "timestamp": "1730000000",
                                    "type": "image",
                                    "image": {"id": "media-abc", "mime_type": "image/jpeg", "sha256": "xyz"},
                                    "caption": "Hoping for a refund",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    raw = json.dumps(payload).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    with client.app.state.SessionLocal() as db:
        message = db.scalar(select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == "wamid.IN.IMG.1"))
        assert message.message_type == "image"
        assert message.body == "[image] Hoping for a refund"
        assert json.loads(message.media_json)["mime_type"] == "image/jpeg"
        assert message.delivery_status == "received"


def test_webhook_post_ignores_own_number(client):
    _configure(client)
    db = client.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.ensure_account()
        account.phone_number_id = "15550000001"
        db.commit()
    finally:
        db.close()
    raw = json.dumps(_text_payload(wa="15550000001", mid="wamid.IN.SELF.1")).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    assert response.json()["new_messages"] == 0


# ---------------------------------------------------------------------------
# Delivery / read status reconciliation
# ---------------------------------------------------------------------------


def test_webhook_statuses_updates_delivery(client):
    _configure(client)
    _seed_outbound(client, whatsapp_message_id="wamid.OUT.0001")
    raw = json.dumps(_statuses_payload("wamid.OUT.0001", "delivered")).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    assert response.json()["statuses_updated"] == 1
    with client.app.state.SessionLocal() as db:
        outbound = db.scalar(select(WhatsAppCSOutbound).where(WhatsAppCSOutbound.whatsapp_message_id == "wamid.OUT.0001"))
        assert outbound.status == "delivered"
        message = db.scalar(
            select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == "wamid.OUT.0001")
        )
        assert message is not None and message.delivery_status == "delivered"


def test_webhook_statuses_does_not_create_customer_message(client):
    _configure(client)
    raw = json.dumps(_statuses_payload("wamid.OUT.UNKNOWN", "read")).encode()
    response = client.post("/api/whatsapp-cs/webhook", content=raw, headers={"X-Hub-Signature-256": _sign(raw)})
    assert response.status_code == 200
    # Unknown wamid: acknowledged, nothing invented.
    with client.app.state.SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(WhatsAppCSMessage))
        assert count == 0


# ---------------------------------------------------------------------------
# AI reply pipeline (reply_worker)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reply_worker_sends_ai_reply(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="What are your hours?")
    gemini = FakeGemini()
    cloud = FakeCloud()
    result = await reply_worker(_state(client, gemini=gemini, cloud=cloud), message_id)
    assert result is True
    assert len(gemini.calls) == 1
    with client.app.state.SessionLocal() as db:
        outbound = db.scalar(select(WhatsAppCSOutbound).order_by(WhatsAppCSOutbound.created_at.desc()).limit(1))
        assert outbound is not None
        assert outbound.status == "sent"
        assert outbound.whatsapp_message_id.startswith("wamid.OUT.")
        conv = db.get(WhatsAppCSConversation, conversation_id)
        assert conv.last_message_at is not None and conv.handling_mode == "ai"
        outgoing = db.scalar(
            select(WhatsAppCSMessage).where(WhatsAppCSMessage.conversation_id == conversation_id,
                                            WhatsAppCSMessage.direction == "outgoing")
        )
        assert outgoing is not None
        assert outgoing.delivery_status == "sent"
    assert cloud.sent and cloud.sent[0]["text"].startswith("Our store hours")


@pytest.mark.anyio
async def test_reply_worker_falls_back_when_model_empty(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="Hi")
    gemini = FakeGemini(text="")
    result = await reply_worker(_state(client, gemini=gemini), message_id)
    assert result is True
    with client.app.state.SessionLocal() as db:
        outbound = db.scalar(select(WhatsAppCSOutbound).order_by(WhatsAppCSOutbound.created_at.desc()).limit(1))
        assert outbound.status == "sent"
        assert "team" in outbound.text.lower()


@pytest.mark.anyio
async def test_reply_worker_escalates_on_human_request_without_llm(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="I want to talk to a human please")
    gemini = FakeGemini()
    result = await reply_worker(_state(client, gemini=gemini), message_id)
    assert result is True
    assert gemini.calls == []  # deterministic escalation never calls the LLM
    with client.app.state.SessionLocal() as db:
        conv = db.get(WhatsAppCSConversation, conversation_id)
        assert conv.handling_mode == "human"
        assert conv.status == "human"
        assert "human" in conv.escalation_reason
        outgoing = db.scalar(
            select(WhatsAppCSMessage).where(WhatsAppCSMessage.conversation_id == conversation_id,
                                            WhatsAppCSMessage.direction == "outgoing")
        )
        assert outgoing is not None and handover_text() in outgoing.body


@pytest.mark.anyio
async def test_reply_worker_respects_persisted_human_takeover(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="Order status?")
    db = client.app.state.SessionLocal()
    try:
        conv = db.get(WhatsAppCSConversation, conversation_id)
        conv.handling_mode = "human"
        conv.status = "human"
        db.commit()
    finally:
        db.close()
    gemini = FakeGemini()
    result = await reply_worker(_state(client, gemini=gemini), message_id)
    assert result is False
    assert gemini.calls == []
    with client.app.state.SessionLocal() as db:
        outbound_count = db.scalar(select(func.count()).select_from(WhatsAppCSOutbound))
        assert outbound_count == 0


@pytest.mark.anyio
async def test_reply_worker_skips_when_ai_disabled(client):
    _configure(client)
    client.app.state.settings.whatsapp_cs_ai_enabled = False
    _, conversation_id, message_id = _seed_incoming(client, body="Hello there")
    gemini = FakeGemini()
    result = await reply_worker(_state(client, gemini=gemini), message_id)
    assert result is False
    assert gemini.calls == []


@pytest.mark.anyio
async def test_reply_worker_loop_guard_skips_echo_of_own_reply(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="What are your hours?", mid="wamid.IN.LOOP.1")
    gemini = FakeGemini(text="We are open 9 to 5.")
    state = _state(client, gemini=gemini)
    first = await reply_worker(state, message_id)
    assert first is True

    # A message that merely echoes our own sent reply must not trigger another reply.
    _, same_conversation_id, echo_id = _seed_incoming(client, body="We are open 9 to 5.", mid="wamid.IN.LOOP.2")
    assert same_conversation_id == conversation_id
    second = await reply_worker(state, echo_id)
    assert second is False
    assert len(gemini.calls) == 1  # the echo never reached the model


@pytest.mark.anyio
async def test_reply_worker_handles_llm_failure_without_claiming_reply(client):
    _configure(client)
    _, conversation_id, message_id = _seed_incoming(client, body="Where is my package?")
    gemini = FakeGemini(error=RuntimeError("provider down"))
    result = await reply_worker(_state(client, gemini=gemini), message_id)
    assert result is None
    with client.app.state.SessionLocal() as db:
        outbound_count = db.scalar(select(func.count()).select_from(WhatsAppCSOutbound))
        assert outbound_count == 0
        conv = db.get(WhatsAppCSConversation, conversation_id)
        assert conv.handling_mode == "ai"  # no automatic handover on provider blip


@pytest.mark.anyio
async def test_reply_worker_send_failure_tracks_transient_vs_permanent(client):
    _configure(client)
    _, _, transient_id = _seed_incoming(client, body="Transient failure test", mid="wamid.IN.TRANS.1")
    transient = FakeCloud(error=WhatsAppCloudAPIError("temporarily blocked", status_code=429, retryable=True))
    result = await reply_worker(_state(client, cloud=transient), transient_id)
    assert result is False
    with client.app.state.SessionLocal() as db:
        outbound = db.scalar(select(WhatsAppCSOutbound).order_by(WhatsAppCSOutbound.created_at.desc()).limit(1))
        assert outbound.status == "failed"  # transient → retryable later, but never auto-duplicated
        assert outbound.retry_count >= 1

    _, _, permanent_id = _seed_incoming(client, body="Permanent failure test", mid="wamid.IN.PERM.1")
    permanent = FakeCloud(
        error=WhatsAppCloudAPIError("invalid message", status_code=400, api_code=131030, retryable=False)
    )
    result = await reply_worker(_state(client, cloud=permanent), permanent_id)
    assert result is False
    with client.app.state.SessionLocal() as db:
        outbound = db.scalar(select(WhatsAppCSOutbound).order_by(WhatsAppCSOutbound.created_at.desc()).limit(1))
        assert outbound.status == "permanent_failed"
        mirror = db.scalar(
            select(WhatsAppCSMessage).where(
                WhatsAppCSMessage.direction == "outgoing",
                WhatsAppCSMessage.idempotency_key == outbound.idempotency_key,
            )
        )
        assert mirror.delivery_status == "failed"


# ---------------------------------------------------------------------------
# Agent behaviour (pure functions)
# ---------------------------------------------------------------------------


def test_detect_escalation_rules():
    assert detect_escalation("Can I talk to a manager?") == (True, "customer requested a human / complaint")
    assert detect_escalation("I need a refund now")[0] is True
    assert detect_escalation("I need a refund now", sensitive_escalation=False)[0] is False
    assert detect_escalation("What are your opening hours?") == (False, "")


def test_decide_escalation_marker_and_uncertainty():
    assert decide_escalation(f"We'll look into this. {ESCALATE_MARKER}", pre_escalated=False, kb_hits=1, settings={})[0] is True
    assert decide_escalation("I'm not sure about that", pre_escalated=False, kb_hits=0,
                             settings={"escalation_enabled": True})[0] is True
    assert decide_escalation("Our hours are 9–5.", pre_escalated=False, kb_hits=2, settings={})[0] is False
    assert decide_escalation("hello", pre_escalated=True, kb_hits=99, settings={})[0] is True


def test_normalize_reply_cleans_and_truncates():
    assert normalize_reply("  hello   world  \n more ") == "hello world more"
    assert normalize_reply("x" * 2000, max_length=100).endswith("…")
    assert normalize_reply("") == ""


def test_build_messages_include_policy_kb_and_context():
    customer = SimpleNamespace(profile_name="Aisha", language="es")
    history = [{"direction": "incoming", "body": "Do you ship to Spain?"}]
    entry = WhatsAppCSKnowledgeEntry(category="shipping", title="Shipping to Spain", body="We ship within 5 days.", tags="")
    messages = build_messages(customer, history, "¿Cuánto tarda?", [entry], {"max_response_length": 600})
    system, user = messages[0]["content"], messages[1]["content"]
    assert "Reply in the customer's language (es)" in system
    assert "Never invent" in system
    assert "untrusted data" in system
    assert "Shipping to Spain" in system
    assert "¿Cuánto tarda?" in user
    assert "Do you ship to Spain?" in user


# ---------------------------------------------------------------------------
# Store: knowledge base retrieval + outbox idempotency
# ---------------------------------------------------------------------------


def test_kb_search_returns_relevant_first(client):
    db = client.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.ensure_account()
        store.kb_create(account.id, category="faq", title="Opening hours", body="We open at 9am.", tags="hours")
        store.kb_create(
            account.id, category="returns", title="Return policy", body="30-day returns on unopened items.", tags="return"
        )
        db.commit()
        hits = store.kb_search(account.id, "return policy what happens")
        assert hits and hits[0].title == "Return policy"
        assert len([h for h in hits if h.title == "Open hours"]) == 0
        inactive = store.kb_create(account.id, category="faq", title="Old policy", body="old", is_active=False)
        db.commit()
        hits = store.kb_search(account.id, "old policy old policy")
        assert inactive.id not in {h.id for h in hits}
    finally:
        db.close()


def test_outbox_idempotency_key_unique(client):
    from sqlalchemy.exc import IntegrityError

    db = client.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.ensure_account()
        db.flush()
        customer = store.get_or_create_customer(account.id, "15550000001", "Aisha")
        conversation = store.get_or_create_conversation(account.id, customer.id)
        store.record_outgoing(
            account, conversation, wa_phone=customer.wa_id, text="first", idempotency_key="dup-key"
        )
        with pytest.raises(IntegrityError):
            store.record_outgoing(
                account, conversation, wa_phone=customer.wa_id, text="second", idempotency_key="dup-key"
            )
        db.rollback()
    finally:
        db.close()


@pytest.mark.anyio
async def test_send_template_composes_meta_body():
    from app.services.whatsapp_cs_cloud import WhatsAppCloudClient

    cloud = WhatsAppCloudClient(access_token="t", phone_number_id="111222333", api_version="v23.0")
    captured = {}

    async def fake_post(url, body):
        captured["url"] = url
        captured["body"] = body
        return {"messages": [{"id": "wamid.TPL.1"}]}

    cloud._post = fake_post
    wamid = await cloud.send_template(
        "15550000001",
        template_name="booking_confirm",
        language_code="en_US",
        components=[{"type": "body", "parameters": [{"type": "text", "text": "Hi"}]}],
    )
    assert wamid == "wamid.TPL.1"
    assert captured["url"].endswith("/111222333/messages")
    assert captured["body"]["type"] == "template"
    assert captured["body"]["template"]["name"] == "booking_confirm"
    assert captured["body"]["template"]["language"] == {"code": "en_US"}
    assert captured["body"]["to"] == "15550000001"


# ---------------------------------------------------------------------------
# Admin API: conversations, handover, knowledge, settings, connection
# ---------------------------------------------------------------------------


def test_admin_endpoints_require_admin(client, admin_headers, exchange):
    _configure(client)
    user_headers = exchange("customer@example.com")

    assert client.get("/api/whatsapp-cs/overview").status_code == 401
    assert client.get("/api/whatsapp-cs/overview", headers=user_headers).status_code == 403
    assert client.get("/api/whatsapp-cs/conversations", headers=user_headers).status_code == 403
    assert client.get("/api/whatsapp-cs/knowledge", headers=user_headers).status_code == 403
    assert client.get("/api/whatsapp-cs/ai-settings", headers=user_headers).status_code == 403
    assert client.get("/api/whatsapp-cs/connection", headers=user_headers).status_code == 403

    # The authenticated-but-non-admin status endpoint is intentionally open.
    assert client.get("/api/whatsapp-cs/status", headers=user_headers).status_code == 200


def test_overview_returns_metrics(client, admin_headers):
    _configure(client)
    _seed_incoming(client, body="Help please")
    response = client.get("/api/whatsapp-cs/overview", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["conversations_total"] == 1
    assert data["active_conversations"] >= 1
    assert data["new_leads_7d"] >= 1
    assert set(data["delivery"]) >= {"pending", "sent", "delivered", "read", "failed"}


def test_conversations_list_and_detail(client, admin_headers):
    _configure(client)
    _, conversation_id, _ = _seed_incoming(client, body="Do you ship internationally?")
    listing = client.get("/api/whatsapp-cs/conversations", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    detail = client.get(f"/api/whatsapp-cs/conversations/{conversation_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["conversation"]["customer"]["profile_name"] == "Aisha"
    assert detail.json()["messages"][0]["body"] == "Do you ship internationally?"


def test_conversation_assign_resume_resolve_reopen(client, admin_headers, exchange):
    _configure(client)
    _, conversation_id, _ = _seed_incoming(client, body="I need help")
    rep_headers = exchange("rep@example.com")  # creates the rep user (non-admin)
    client.get("/api/auth/me", headers=rep_headers)

    assigned = client.post(
        f"/api/whatsapp-cs/conversations/{conversation_id}/assign",
        headers=admin_headers,
        json={"rep_email": "rep@example.com"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["handling_mode"] == "human"
    assert assigned.json()["assigned_rep_name"] == "rep@example.com"

    resume = client.post(f"/api/whatsapp-cs/conversations/{conversation_id}/resume-ai", headers=admin_headers)
    assert resume.status_code == 200
    assert resume.json()["handling_mode"] == "ai"
    assert resume.json()["status"] == "open"

    resolved = client.post(f"/api/whatsapp-cs/conversations/{conversation_id}/resolve", headers=admin_headers)
    assert resolved.status_code == 200 and resolved.json()["status"] == "resolved"

    reopened = client.post(f"/api/whatsapp-cs/conversations/{conversation_id}/reopen", headers=admin_headers)
    assert reopened.status_code == 200 and reopened.json()["status"] == "open"


def test_conversation_notes(client, admin_headers):
    _configure(client)
    _, conversation_id, _ = _seed_incoming(client, body="Question about billing")
    response = client.post(
        f"/api/whatsapp-cs/conversations/{conversation_id}/notes",
        headers=admin_headers,
        json={"text": "Waiting on the customer's invoice"},
    )
    assert response.status_code == 200
    assert "Waiting on the customer's invoice" in response.json()["notes"]
    assert "nwabjd@gmail.com" in response.json()["notes"]


def test_manual_reply_sends_and_marks_human(client, admin_headers):
    _configure(client)
    _, conversation_id, _ = _seed_incoming(client, body="Where is my order?")
    client.app.state.whatsapp_cs_cloud = FakeCloud()
    response = client.post(
        f"/api/whatsapp-cs/conversations/{conversation_id}/reply",
        headers=admin_headers,
        json={"text": "Thanks for waiting — your order is on the way."},
    )
    assert response.status_code == 200
    assert response.json()["message"]["delivery_status"] == "sent"
    detail = client.get(f"/api/whatsapp-cs/conversations/{conversation_id}", headers=admin_headers).json()
    assert detail["conversation"]["handling_mode"] == "human"
    assert detail["conversation"]["assigned_rep_name"] == "nwabjd@gmail.com"


def test_manual_reply_marks_failed_when_api_down(client, admin_headers):
    _configure(client)
    _, conversation_id, _ = _seed_incoming(client, body="Is it in stock?")
    client.app.state.whatsapp_cs_cloud = FakeCloud(
        error=WhatsAppCloudAPIError("token expired", status_code=401, api_code=190, retryable=False)
    )
    response = client.post(
        f"/api/whatsapp-cs/conversations/{conversation_id}/reply",
        headers=admin_headers,
        json={"text": "It is in stock."},
    )
    assert response.status_code == 502


def test_knowledge_crud_and_toggle(client, admin_headers):
    _configure(client)
    created = client.post(
        "/api/whatsapp-cs/knowledge",
        headers=admin_headers,
        json={"category": "shipping", "title": "Shipping times", "body": "3–5 business days.", "tags": "shipping usa"},
    )
    assert created.status_code == 200
    kb_id = created.json()["id"]

    listing = client.get("/api/whatsapp-cs/knowledge", headers=admin_headers)
    assert listing.status_code == 200
    assert any(item["id"] == kb_id for item in listing.json()["items"])

    updated = client.put(
        f"/api/whatsapp-cs/knowledge/{kb_id}",
        headers=admin_headers,
        json={"body": "2–4 business days for expedited orders."},
    )
    assert updated.status_code == 200
    assert "expedited" in updated.json()["body"]

    toggled = client.post(f"/api/whatsapp-cs/knowledge/{kb_id}/toggle", headers=admin_headers)
    assert toggled.status_code == 200 and toggled.json()["is_active"] is False

    deleted = client.delete(f"/api/whatsapp-cs/knowledge/{kb_id}", headers=admin_headers)
    assert deleted.status_code == 200
    listing = client.get("/api/whatsapp-cs/knowledge", headers=admin_headers).json()
    assert all(item["id"] != kb_id for item in listing["items"])


def test_ai_settings_roundtrip(client, admin_headers):
    _configure(client)
    initial = client.get("/api/whatsapp-cs/ai-settings", headers=admin_headers)
    assert initial.status_code == 200
    assert initial.json()["provider"] == "gemini"
    assert initial.json()["enabled"] is True

    updated = client.put(
        "/api/whatsapp-cs/ai-settings",
        headers=admin_headers,
        json={"max_response_length": 400, "fallback": "We'll reply shortly.", "sensitive_escalation": False},
    )
    assert updated.status_code == 200
    assert updated.json()["max_response_length"] == 400
    assert updated.json()["fallback"] == "We'll reply shortly."
    assert updated.json()["sensitive_escalation"] is False

    bad = client.put("/api/whatsapp-cs/ai-settings", headers=admin_headers, json={"provider": "claude"})
    assert bad.status_code == 422


def test_connection_status_never_exposes_secrets(client, admin_headers):
    _configure(client)
    response = client.get("/api/whatsapp-cs/connection", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body)
    assert "access-token-test" not in serialized
    assert APP_SECRET not in serialized
    assert VERIFY_TOKEN not in serialized
    assert body["has_access_token"] is True
    assert body["has_app_secret"] is True
    assert body["has_verify_token"] is True
    assert "token" not in body and "secret" not in body

    status = client.get("/api/whatsapp-cs/status", headers=admin_headers)
    assert json.dumps(status.json()).find("access-token-test") == -1


def test_connection_update_recomputes_status(client, admin_headers):
    _configure(client)
    client.app.state.settings.whatsapp_cs_access_token = None
    updated = client.put(
        "/api/whatsapp-cs/connection",
        headers=admin_headers,
        json={"phone_number_id": "999888777", "business_account_id": "888777666"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "incomplete"  # token missing → not verified

    client.app.state.settings.whatsapp_cs_access_token = "token-present"
    client.app.state.settings.whatsapp_cs_app_secret = APP_SECRET
    client.app.state.settings.whatsapp_cs_verify_token = VERIFY_TOKEN
    verified = client.put(
        "/api/whatsapp-cs/connection",
        headers=admin_headers,
        json={"phone_number_id": "999888777", "business_account_id": "888777666", "display_name": "SALAR Support"},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["display_name"] == "SALAR Support"


# ---------------------------------------------------------------------------
# Webhook pipeline unit (no HTTP)
# ---------------------------------------------------------------------------


def test_process_webhook_payload_unit_idempotency(client):
    _configure(client)
    state = _state(client)
    payload = _text_payload(body="Hello there")
    first = process_webhook_payload(state, payload)
    second = process_webhook_payload(state, payload)
    assert first["ok"] is True and len(first["new_messages"]) == 1
    assert second["new_messages"] == []
    assert process_webhook_payload(state, {"object": "instagram"})["ignored"] == "object"