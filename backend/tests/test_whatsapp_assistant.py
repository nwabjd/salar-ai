from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.whatsapp import _auto_reply, build_auto_reply_messages, normalize_auto_reply
from app.models import AuditEvent, User, WhatsAppContactState
from app.services.whatsapp_conversations import WhatsAppConversationStore


def test_whatsapp_first_reply_introduces_jds_assistant():
    messages = build_auto_reply_messages("Aisha", "Hello", False, introduced=False, history=[])
    assert "introduce yourself briefly as JD's assistant" in messages[0]["content"]


def test_whatsapp_later_reply_forbids_reintroduction_and_includes_history():
    history = [
        {"role": "sender", "text": "Can JD review the proposal?"},
        {"role": "assistant", "text": "Certainly. What deadline are you working with?"},
    ]
    messages = build_auto_reply_messages("Aisha", "Tomorrow", False, introduced=True, history=history)
    prompt = messages[0]["content"]
    assert "Never introduce yourself again" in prompt
    assert "Can JD review the proposal?" in prompt
    assert "What deadline are you working with?" in prompt


def test_whatsapp_fallback_does_not_repeat_introduction():
    first, _ = normalize_auto_reply("", introduced=False)
    later, _ = normalize_auto_reply("", introduced=True)
    assert first.startswith("Hello, this is JD's assistant")
    assert later == "How may I help you?"


def test_whatsapp_first_reply_enforces_introduction_if_model_omits_it():
    reply, _ = normalize_auto_reply("Your delivery is scheduled for Tuesday.", introduced=False)
    assert reply == "Hello, this is JD's assistant. Your delivery is scheduled for Tuesday."


def test_whatsapp_later_reply_strips_a_repeated_model_introduction():
    reply, _ = normalize_auto_reply(
        "Hello, this is JD's assistant. Your delivery is scheduled for Tuesday.",
        introduced=True,
    )
    assert reply == "Your delivery is scheduled for Tuesday."


def test_contact_state_is_per_owner_and_contact(client, exchange):
    headers_a = exchange("owner-a@example.com")
    headers_b = exchange("owner-b@example.com")
    user_a = client.get("/api/auth/me", headers=headers_a).json()
    user_b = client.get("/api/auth/me", headers=headers_b).json()

    with client.app.state.SessionLocal() as db:
        store = WhatsAppConversationStore(db)
        state_a = store.get_or_create(user_a["id"], "15550001@s.whatsapp.net", "Aisha")
        state_b = store.get_or_create(user_b["id"], "15550001@s.whatsapp.net", "Aisha")
        store.record_exchange(state_a, "Hello", "Hello, this is JD's assistant.", introduced=True)
        db.commit()

        saved_a = db.get(WhatsAppContactState, state_a.id)
        saved_b = db.get(WhatsAppContactState, state_b.id)

    assert saved_a.introduced is True
    assert saved_b.introduced is False


def test_store_handles_malformed_history_and_keeps_recent_normalized_turns(client, exchange):
    headers = exchange("history@example.com")
    user = client.get("/api/auth/me", headers=headers).json()
    with client.app.state.SessionLocal() as db:
        state = WhatsAppContactState(
            user_id=user["id"], contact_jid="history@s.whatsapp.net", history_json="not-json"
        )
        db.add(state)
        db.flush()
        store = WhatsAppConversationStore(db)
        assert store.history(state) == []
        for index in range(5):
            store.record_exchange(state, f" incoming {index} ", f" reply {index} ", introduced=index == 0)
        db.commit()
        saved = db.get(WhatsAppContactState, state.id)

    history = WhatsAppConversationStore.history(saved)
    assert len(history) == 8
    assert history[0] == {"role": "sender", "text": "incoming 1"}
    assert history[-1] == {"role": "assistant", "text": "reply 4"}
    assert saved.introduced is True


@pytest.mark.anyio
async def test_successful_send_records_contact_state_and_pass_message_audit(client, exchange):
    headers = exchange("success@example.com")
    user = client.get("/api/auth/me", headers=headers).json()

    class FakeGemini:
        async def chat_with_tools(self, messages, tools):
            return {"text": "GOTOPASS: Please ask JD to call me tomorrow."}

    class FakeWhatsApp:
        async def send_message(self, **kwargs):
            return {"ok": True}

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=FakeGemini()),
        whatsapp=FakeWhatsApp(),
    )
    await _auto_reply(state, user["id"], "15550002@s.whatsapp.net", "Aisha", "Please tell JD", False)

    with client.app.state.SessionLocal() as db:
        contact = db.scalar(select(WhatsAppContactState).where(WhatsAppContactState.user_id == user["id"]))
        audits = list(db.scalars(select(AuditEvent).where(
            AuditEvent.user_id == user["id"],
            AuditEvent.action.in_(["whatsapp.auto_reply", "whatsapp.pass_message"]),
        )))
    assert contact is not None and contact.introduced is True
    assert len(WhatsAppConversationStore.history(contact)) == 2
    assert {event.action for event in audits} == {"whatsapp.auto_reply", "whatsapp.pass_message"}


@pytest.mark.anyio
async def test_failed_send_does_not_mark_contact_introduced(client, exchange):
    headers = exchange("failed-send@example.com")
    user = client.get("/api/auth/me", headers=headers).json()

    class FakeGemini:
        async def chat_with_tools(self, messages, tools):
            return {"text": "Hello, this is JD's assistant. How may I help?"}

    class FailingWhatsApp:
        async def send_message(self, **kwargs):
            return {"error": "offline"}

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=FakeGemini()),
        whatsapp=FailingWhatsApp(),
    )
    await _auto_reply(state, user["id"], "15550003@s.whatsapp.net", "Aisha", "Hello", False)

    with client.app.state.SessionLocal() as db:
        saved = db.scalar(select(WhatsAppContactState).where(
            WhatsAppContactState.user_id == user["id"],
            WhatsAppContactState.contact_jid == "15550003@s.whatsapp.net",
        ))
    assert saved is None or saved.introduced is False
