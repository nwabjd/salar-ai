"""Webhook ingestion + reply pipeline for WhatsApp Customer Service.

This module is deliberately framework-light so it can be unit-tested with a
SimpleNamespace-style ``state`` (SessionLocal, settings, coordinator, cloud
client) exactly like the existing WhatsApp auto-reply tests.

Flow (see docs/whatsapp-customer-service.md for the full pipeline):
1. Route validates the X-Hub-Signature-256 (engine assumes that already ran).
2. ``process_webhook_payload`` — idempotently persists incoming messages and
   reconciles delivery/read statuses. Synchronous and fast so the webhook can
   acknowledge Meta promptly.
3. The route schedules asyncio tasks for each NEW message id -> ``reply_worker``.
4. ``reply_worker`` runs the AI agent off the request path, then sends through
   the outbox (an idempotency key is always created BEFORE the external call so
   a crash can never double-send) and records the outcome.
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Dict, List, Optional

from ..models import (
    AuditEvent,
    WhatsAppCSAccount,
    WhatsAppCSConversation,
    WhatsAppCSMessage,
    utcnow,
)
from .whatsapp_cs_agent import (
    build_messages,
    decide_escalation,
    detect_escalation,
    handover_text,
    normalize_reply,
    strip_escalate_marker,
)
from .whatsapp_cs_cloud import WhatsAppCloudAPIError
from .whatsapp_cs_store import WhatsAppCSStore

log = logging.getLogger(__name__)

_SUPPORTED_MEDIA = {"image", "video", "document", "audio", "sticker", "location", "contacts"}


# ---------------------------------------------------------------------------
# Webhook payload ingestion (synchronous)
# ---------------------------------------------------------------------------


def process_webhook_payload(state, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist inbound messages + reconcile statuses. Returns a summary.

    Safe to call twice for the same delivery: message ids are unique and the
    webhook-event ledger makes re-processing a no-op.
    """
    if not isinstance(payload, dict):
        return {"ok": True, "ignored": "malformed"}
    if payload.get("object") != "whatsapp_business_account":
        return {"ok": True, "ignored": "object"}

    db = state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        account = store.get_account()
        if account is None:
            account = store.ensure_account()
            db.flush()
        ai = store.get_ai_settings(account.id, state.settings)
        default_mode = "ai" if ai.get("env_enabled") else "human"

        new_message_ids: List[str] = []
        statuses_updated = 0

        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                contacts = {c.get("wa_id"): c for c in (value.get("contacts") or []) if isinstance(c, dict)}
                messages = value.get("messages") if isinstance(value.get("messages"), list) else []
                statuses = value.get("statuses") if isinstance(value.get("statuses"), list) else []

                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    mid = str(msg.get("id") or "").strip()
                    from_wa = str(msg.get("from") or "").strip()
                    if not mid or not from_wa:
                        continue
                    # Never treat our own number as a customer (loop safety).
                    if account.phone_number_id and from_wa == account.phone_number_id:
                        continue
                    if store.webhook_event_exists(mid):
                        continue

                    profile = contacts.get(from_wa) or {}
                    profile_name = ""
                    language = ""
                    if isinstance(profile, dict):
                        profile_name = (profile.get("profile") or {}).get("name", "")
                        language = profile.get("language", "")

                    mtype = str(msg.get("type") or "text")
                    body, media = _extract_message_content(mtype, msg)

                    customer = store.get_or_create_customer(account.id, from_wa, profile_name, language)
                    conversation = store.get_or_create_conversation(account.id, customer.id, default_mode=default_mode)
                    message, created = store.persist_incoming(
                        account.id,
                        conversation.id,
                        external_message_id=mid,
                        message_type=mtype,
                        body=body,
                        media=media,
                    )
                    if created and message is not None:
                        conversation.last_message_at = message.created_at or utcnow()
                        new_message_ids.append(message.id)

                for st in statuses:
                    if not isinstance(st, dict):
                        continue
                    sid = str(st.get("id") or "").strip()
                    sstatus = str(st.get("status") or "").lower()
                    if not sid:
                        continue
                    error = _status_error_text(st.get("errors"))
                    if store.reconcile_delivery(sid, sstatus, error):
                        statuses_updated += 1

        db.commit()
        return {"ok": True, "new_messages": new_message_ids, "statuses_updated": statuses_updated}
    except Exception:
        db.rollback()
        log.exception("whatsapp-cs webhook payload processing failed")
        raise
    finally:
        db.close()


def _extract_message_content(mtype: str, msg: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    if mtype == "text":
        body = ""
        text = msg.get("text")
        if isinstance(text, dict):
            body = text.get("body") or ""
        return str(body), {}
    if mtype in _SUPPORTED_MEDIA:
        media_obj = msg.get(mtype)
        if not isinstance(media_obj, dict):
            media_obj = {}
        media = {
            k: v
            for k, v in media_obj.items()
            if k in ("id", "mime_type", "sha256", "filename", "caption", "latitude", "longitude", "name", "address")
        }
        caption = media_obj.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            top_caption = msg.get("caption")
            caption = top_caption if isinstance(top_caption, str) else ""
        caption = caption.strip()
        body = f"[{mtype}] {caption}" if caption else f"[{mtype}]"
        return body, media
    body = msg.get("text")
    if isinstance(body, dict):
        body = body.get("body") or ""
    body = str(body).strip()
    return (f"[{mtype}] {body}" if body else f"[{mtype}]"), {}


def _status_error_text(errors: Any) -> str:
    if not isinstance(errors, list):
        return ""
    parts = []
    for e in errors:
        if not isinstance(e, dict):
            continue
        parts.append(str(e.get("message") or e.get("title") or e.get("code") or ""))
    return "; ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Reply worker (async, runs off the webhook request path)
# ---------------------------------------------------------------------------


async def reply_worker(state, message_id: str) -> Optional[bool]:
    """Generate + send the AI reply for one incoming message.

    Returns True if a message was sent, False if it was skipped, None on
    transient errors that should not retry automatically (dedupe stays intact).
    """
    db = state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        message = db.get(WhatsAppCSMessage, message_id)
        if message is None or message.direction != "incoming":
            return None
        conversation = store.get_conversation(message.conversation_id)
        if conversation is None:
            return None
        # Human takeover and AI pause are persisted on the conversation row, so
        # they survive restarts and always block automatic replies.
        if conversation.handling_mode != "ai":
            return False
        account = db.get(WhatsAppCSAccount, message.account_id)
        if account is None:
            return None
        ai = store.get_ai_settings(account.id, state.settings)
        if not ai.get("enabled") or not ai.get("env_enabled") or ai.get("provider") != "gemini":
            return False

        incoming_text = (message.body or "").strip()
        if not incoming_text:
            return False
        # Loop guard: never reply to a message that is an echo of something we
        # already sent (prevents automated response loops).
        if store.has_recent_outgoing_reply(conversation.id, incoming_text, window_minutes=2):
            log.info("whatsapp-cs loop guard: skipping echo of our own reply %s", message.id)
            return False

        customer = store.get_customer(conversation.customer_id)

        escalated_pre, reason_pre = detect_escalation(
            incoming_text, sensitive_escalation=bool(ai.get("sensitive_escalation"))
        )
        if escalated_pre:
            return await _escalate(state, store, db, account, conversation, message, ai, reason_pre)

        kb_entries = store.kb_search(account.id, incoming_text, limit=5)
        history = [
            {"direction": m.direction, "body": m.body}
            for m in store.conversation_messages(conversation.id, limit=16)
        ]
        messages = build_messages(customer, history, incoming_text, kb_entries, ai)

        gemini = getattr(getattr(state, "coordinator", None), "gemini", None)
        if gemini is None:
            log.warning("whatsapp-cs reply skipped: no LLM client available")
            return None
        try:
            result = await gemini.chat_with_tools(messages, [])
        except Exception as exc:
            # Provider failure: never claim a reply was sent.
            log.warning("whatsapp-cs LLM call failed (%s)", type(exc).__name__)
            return None

        reply = result.get("text", "") if isinstance(result, dict) else ""
        escalate, reason = decide_escalation(reply, pre_escalated=False, kb_hits=len(kb_entries), settings=ai)
        reply_clean = strip_escalate_marker(normalize_reply(reply, int(ai.get("max_response_length") or 600)))

        if escalate:
            store.set_handling_mode(conversation, "human", reason=reason)
            if not reply_clean:
                reply_clean = handover_text()
            db.commit()
            sent = await _send_text(state, store, db, account, conversation, message, reply_clean)
            _audit(db, None, "whatsapp_cs.escalated", {"conversation_id": conversation.id, "reason": reason, "sent": sent})
            db.commit()
            return True

        if not reply_clean:
            fallback = ai.get("fallback") or ""
            reply_clean = normalize_reply(fallback, int(ai.get("max_response_length") or 600))
            if not reply_clean:
                return None
        return await _send_text(state, store, db, account, conversation, message, reply_clean)
    except Exception:
        db.rollback()
        log.exception("whatsapp-cs reply worker failed for message %s", message_id)
        return None
    finally:
        db.close()


async def _escalate(state, store, db, account, conversation, message, ai, reason: str) -> bool:
    """Deterministic handover on explicit customer request (no LLM call)."""
    store.set_handling_mode(conversation, "human", reason=reason)
    db.commit()
    sent = await _send_text(state, store, db, account, conversation, message, handover_text())
    _audit(db, None, "whatsapp_cs.escalated", {"conversation_id": conversation.id, "reason": reason, "sent": sent})
    db.commit()
    return True


async def _send_text(state, store, db, account: WhatsAppCSAccount, conversation: WhatsAppCSConversation, incoming: WhatsAppCSMessage, reply_text: str) -> bool:
    client = getattr(state, "whatsapp_cs_cloud", None)
    customer = store.get_customer(conversation.customer_id)
    if client is None or customer is None:
        return False
    wa_phone = customer.wa_id
    idem = f"in-{incoming.id}-{secrets.token_urlsafe(8)}"
    # Persist the idempotent outbox row BEFORE calling the external API so a
    # crash mid-send can never create a duplicate customer-visible message.
    outbound = store.record_outgoing(
        account, conversation, wa_phone=wa_phone, text=reply_text, message_type="text", idempotency_key=idem
    )[0]
    db.commit()
    try:
        wamid = await client.send_text(wa_phone, reply_text)
    except WhatsAppCloudAPIError as exc:
        store.mark_outbound_failed(outbound, exc.message, permanent=not exc.retryable)
        db.commit()
        log.warning("whatsapp-cs send failed (retryable=%s): %s", exc.retryable, exc.message[:200])
        return False
    except Exception as exc:  # unexpected (network, etc.)
        store.mark_outbound_failed(outbound, f"unexpected {type(exc).__name__}", permanent=False)
        db.commit()
        log.warning("whatsapp-cs unexpected send failure: %s", type(exc).__name__)
        return False
    store.mark_outbound_sent(outbound, wamid)
    conversation.last_message_at = utcnow()
    _audit(db, None, "whatsapp_cs.sent", {"conversation_id": conversation.id, "wamid": wamid})
    db.commit()
    return True


def _audit(db, user_id: Optional[str], action: str, detail: Dict[str, Any]) -> None:
    try:
        db.add(AuditEvent(user_id=user_id, action=action, detail_json=json.dumps(detail, default=str)[:4000]))
    except Exception:  # pragma: no cover - audit must never break the pipeline
        log.warning("whatsapp-cs audit write failed for %s", action)