import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.whatsapp import _auto_reply, build_auto_reply_messages, normalize_auto_reply
from app.models import AuditEvent, User, WhatsAppContactState
from app.services.whatsapp_conversations import WhatsAppConversationStore
from app.models import utcnow


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


@pytest.mark.parametrize(("model_reply", "expected"), [
    ("This is JD's assistant. Your delivery is scheduled for Tuesday.", "Your delivery is scheduled for Tuesday."),
    ("I'm JD's assistant. Your delivery is scheduled for Tuesday.", "Your delivery is scheduled for Tuesday."),
    ("I am JD's assistant. Your delivery is scheduled for Tuesday.", "Your delivery is scheduled for Tuesday."),
    ("As JD's assistant, your delivery is scheduled for Tuesday.", "your delivery is scheduled for Tuesday."),
    ("JD's assistant here: Your delivery is scheduled for Tuesday.", "Your delivery is scheduled for Tuesday."),
    ("Hi, I’m JD’s assistant — Your delivery is scheduled for Tuesday.", "Your delivery is scheduled for Tuesday."),
    ("As JD's assistant", "How may I help you?"),
])
def test_whatsapp_later_reply_strips_common_leading_identity_prefixes(model_reply, expected):
    reply, _ = normalize_auto_reply(model_reply, introduced=True)
    assert reply == expected


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


@pytest.mark.anyio
async def test_overlapping_auto_replies_serialize_contact_state(client, exchange):
    headers = exchange("overlap@example.com")
    user = client.get("/api/auth/me", headers=headers).json()
    first_model_started = asyncio.Event()
    allow_first_model = asyncio.Event()
    second_invoked = asyncio.Event()
    second_model_started = asyncio.Event()
    model_prompts = []
    sent = []

    class FakeGemini:
        async def chat_with_tools(self, messages, tools):
            model_prompts.append(messages)
            if len(model_prompts) == 1:
                first_model_started.set()
                await allow_first_model.wait()
                return {"text": "First reply."}
            second_model_started.set()
            return {"text": "Second reply."}

    class FakeWhatsApp:
        async def send_message(self, **kwargs):
            sent.append(kwargs["text"])
            return {"ok": True}

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=FakeGemini()),
        whatsapp=FakeWhatsApp(),
    )

    first = asyncio.create_task(_auto_reply(
        state, user["id"], "15550004@s.whatsapp.net", "Aisha", "First", False,
    ))
    await first_model_started.wait()

    async def second_reply():
        second_invoked.set()
        await _auto_reply(state, user["id"], "15550004@s.whatsapp.net", "Aisha", "Second", False)

    second = asyncio.create_task(second_reply())
    await second_invoked.wait()
    assert second_model_started.is_set() is False
    allow_first_model.set()
    await asyncio.gather(first, second)

    with client.app.state.SessionLocal() as db:
        contact = db.scalar(select(WhatsAppContactState).where(
            WhatsAppContactState.user_id == user["id"],
            WhatsAppContactState.contact_jid == "15550004@s.whatsapp.net",
        ))

    assert sum("JD's assistant" in text for text in sent) == 1
    assert [item["content"] for item in model_prompts[1] if item["role"] == "system"][0].count("First") >= 1
    assert WhatsAppConversationStore.history(contact) == [
        {"role": "sender", "text": "First"},
        {"role": "assistant", "text": sent[0]},
        {"role": "sender", "text": "Second"},
        {"role": "assistant", "text": sent[1]},
    ]
    assert state._whatsapp_contact_locks._entries == {}


def test_reply_lease_serializes_two_store_sessions_without_history_overwrite(client, exchange):
    headers = exchange("lease@example.com")
    user = client.get("/api/auth/me", headers=headers).json()
    jid = "15550005@s.whatsapp.net"

    with client.app.state.SessionLocal() as db_first:
        first = WhatsAppConversationStore(db_first)
        snapshot = first.acquire_reply_lease(user["id"], jid, "Aisha", "first-token")
        assert snapshot is not None
        db_first.commit()

    with client.app.state.SessionLocal() as db_second:
        second = WhatsAppConversationStore(db_second)
        assert second.acquire_reply_lease(user["id"], jid, "Aisha", "second-token") is None
        db_second.rollback()

    with client.app.state.SessionLocal() as db_first:
        first = WhatsAppConversationStore(db_first)
        assert first.complete_reply(
            user["id"], jid, "first-token", "First", "First reply.", introduced=True,
        ) is True
        db_first.commit()

    with client.app.state.SessionLocal() as db_second:
        second = WhatsAppConversationStore(db_second)
        snapshot = second.acquire_reply_lease(user["id"], jid, "Aisha", "second-token")
        assert snapshot is not None and snapshot.introduced is True
        assert second.complete_reply(
            user["id"], jid, "second-token", "Second", "Second reply.", introduced=True,
        ) is True
        db_second.commit()

    with client.app.state.SessionLocal() as db:
        saved = db.scalar(select(WhatsAppContactState).where(WhatsAppContactState.user_id == user["id"]))
    assert WhatsAppConversationStore.history(saved) == [
        {"role": "sender", "text": "First"},
        {"role": "assistant", "text": "First reply."},
        {"role": "sender", "text": "Second"},
        {"role": "assistant", "text": "Second reply."},
    ]


def test_reply_lease_recovers_stale_token(client, exchange):
    headers = exchange("stale-lease@example.com")
    user = client.get("/api/auth/me", headers=headers).json()
    jid = "15550006@s.whatsapp.net"
    with client.app.state.SessionLocal() as db:
        store = WhatsAppConversationStore(db)
        assert store.acquire_reply_lease(user["id"], jid, "Aisha", "stale-token") is not None
        db.commit()
        contact = db.scalar(select(WhatsAppContactState).where(WhatsAppContactState.user_id == user["id"]))
        contact.reply_lease_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()

    with client.app.state.SessionLocal() as db:
        store = WhatsAppConversationStore(db)
        contact = store.acquire_reply_lease(user["id"], jid, "Aisha", "fresh-token")
        assert contact is not None and contact.reply_lease_token == "fresh-token"


@pytest.mark.anyio
async def test_cancelled_auto_reply_releases_its_reply_lease(client, exchange):
    headers = exchange("cancel-lease@example.com")
    user = client.get("/api/auth/me", headers=headers).json()
    model_started = asyncio.Event()

    class BlockingGemini:
        async def chat_with_tools(self, messages, tools):
            model_started.set()
            await asyncio.Event().wait()

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=BlockingGemini()),
        whatsapp=SimpleNamespace(),
    )
    task = asyncio.create_task(_auto_reply(
        state, user["id"], "15550007@s.whatsapp.net", "Aisha", "Hello", False,
    ))
    await model_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    with client.app.state.SessionLocal() as db:
        contact = db.scalar(select(WhatsAppContactState).where(WhatsAppContactState.user_id == user["id"]))
    assert contact.reply_lease_token is None


@pytest.mark.anyio
@pytest.mark.parametrize("send_result", [None, {}, {"ok": False}, {"error": "offline"}, {"ok": True, "error": "offline"}])
async def test_unsuccessful_send_results_do_not_persist_contact_state(client, exchange, send_result):
    headers = exchange(f"send-result-{str(send_result)}@example.com")
    user = client.get("/api/auth/me", headers=headers).json()

    class FakeGemini:
        async def chat_with_tools(self, messages, tools):
            return {"text": "Hello"}

    class FakeWhatsApp:
        async def send_message(self, **kwargs):
            return send_result

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=FakeGemini()),
        whatsapp=FakeWhatsApp(),
    )
    await _auto_reply(state, user["id"], "15550008@s.whatsapp.net", "Aisha", "Hello", False)

    with client.app.state.SessionLocal() as db:
        contact = db.scalar(select(WhatsAppContactState).where(WhatsAppContactState.user_id == user["id"]))
        auto_reply = db.scalar(select(AuditEvent).where(
            AuditEvent.user_id == user["id"], AuditEvent.action == "whatsapp.auto_reply",
        ))
    assert contact is None or (contact.introduced is False and WhatsAppConversationStore.history(contact) == [])
    assert auto_reply is None
