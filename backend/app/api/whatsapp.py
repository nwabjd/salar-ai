import asyncio
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..models import AuditEvent, User
from ..security import get_current_user
from ..services.whatsapp_conversations import WhatsAppConversationStore

log = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])


class _ContactLockPool:
    def __init__(self):
        self._entries = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def hold(self, key):
        async with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = {"lock": asyncio.Lock(), "references": 0}
                self._entries[key] = entry
            entry["references"] += 1

        acquired = False
        try:
            await entry["lock"].acquire()
            acquired = True
            yield
        finally:
            if acquired:
                entry["lock"].release()
            async with self._guard:
                entry["references"] -= 1
                if entry["references"] == 0 and not entry["lock"].locked():
                    self._entries.pop(key, None)


def _contact_locks(state):
    pool = getattr(state, "_whatsapp_contact_locks", None)
    if pool is None:
        pool = _ContactLockPool()
        setattr(state, "_whatsapp_contact_locks", pool)
    return pool


_REPEATED_ASSISTANT_IDENTITY = re.compile(
    r"^\s*(?:(?:hello|hi|hey)[,!]?\s*)?(?:(?:this\s+is|i\s*(?:am|['\u2019]m)|as)\s+)?"
    r"jd(?:['\u2019]s|s)\s+assistant(?:\s+here)?[\s.,!:\-\u2013\u2014]*",
    flags=re.IGNORECASE,
)


async def _acquire_reply_lease(state, user_id, from_jid, sender_name, lease_token):
    for _ in range(40):
        db = state.SessionLocal()
        try:
            store = WhatsAppConversationStore(db)
            contact = store.acquire_reply_lease(user_id, from_jid, sender_name, lease_token)
            if contact is not None:
                snapshot = (contact.introduced, store.history(contact))
                db.commit()
                return snapshot
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(0.05)
    return None


def _release_reply_lease(state, user_id, from_jid, lease_token):
    db = state.SessionLocal()
    try:
        store = WhatsAppConversationStore(db)
        if store.release_reply_lease(user_id, from_jid, lease_token):
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        log.warning("Auto-reply lease release failed")
    finally:
        db.close()


def _complete_auto_reply(state, user_id, from_jid, sender_name, text, reply_text, pass_msg, lease_token):
    db = state.SessionLocal()
    try:
        store = WhatsAppConversationStore(db)
        if not store.complete_reply(user_id, from_jid, lease_token, text, reply_text, introduced=True):
            db.rollback()
            return False
        db.add(AuditEvent(
            user_id=user_id,
            action="whatsapp.auto_reply",
            detail_json=json.dumps({
                "to": from_jid, "sender_name": sender_name,
                "incoming": text[:300], "reply": reply_text[:300],
            }),
        ))
        if pass_msg:
            db.add(AuditEvent(
                user_id=user_id,
                action="whatsapp.pass_message",
                detail_json=json.dumps({
                    "from": from_jid, "sender_name": sender_name,
                    "message": pass_msg[:500], "acknowledged": False,
                }),
            ))
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class WhatsAppSendRequest(BaseModel):
    to: Optional[str] = None
    phone: Optional[str] = None
    text: str


class WhatsAppWebhook(BaseModel):
    user_id: Optional[str] = None
    from_: str = Field(alias="from")
    sender_name: str
    text: str
    is_group: bool = False
    timestamp: int = 0


class WhatsAppAutoReplyToggle(BaseModel):
    enabled: bool


def build_auto_reply_messages(sender_name: str, text: str, is_group: bool, introduced: bool, history):
    context = f"WhatsApp {'group' if is_group else 'DM'} message from {sender_name}: {text}"
    history_text = "\n".join(
        f"{item['role']}: {item['text']}"
        for item in history[-8:]
        if item.get("role") in {"sender", "assistant"} and item.get("text")
    )
    identity_rule = (
        "This is the first reply to this contact. You must introduce yourself briefly as JD's assistant once, then help."
        if not introduced
        else "This contact already knows you are JD's assistant. Never introduce yourself again; continue naturally from the conversation."
    )
    policy = (
        "You are replying professionally to a WhatsApp sender on JD's behalf. Never pretend to be JD and never "
        "introduce yourself as an AI. "
        f"{identity_rule} "
        "Address specific queries directly. Ask one focused question only when essential details are missing. "
        "Do not fabricate facts, promises, availability, prices, dates, or actions. "
        "Use a warm, authentic, professional tone in one to three short plain-text sentences. "
        "If the sender asks to speak with JD, offer to help first and ask for the purpose or key details. "
        "If the sender explicitly asks you to tell JD something or pass a message, respond only with "
        "GOTOPASS: followed by the exact concise message for JD. Use GOTOPASS only for explicit pass-message requests."
    )
    if history_text:
        policy += f"\n\nRecent conversation:\n{history_text}"
    return [{"role": "system", "content": policy}, {"role": "user", "content": context}]


def normalize_auto_reply(reply_text: str, introduced: bool):
    clean = (reply_text or "").strip()
    if not clean:
        clean = "How may I help you?"
    pass_message = None
    if clean.startswith("GOTOPASS:"):
        pass_message = clean[len("GOTOPASS:"):].strip() or None
        clean = "Thank you. I'll make sure JD receives your message. Is there anything else I can help you with?"
    if introduced:
        clean = _REPEATED_ASSISTANT_IDENTITY.sub("", clean).strip()
        if not clean:
            clean = "How may I help you?"
    elif not re.search(r"\bjd(?:['\u2019]s|s)\s+assistant\b", clean, flags=re.IGNORECASE):
        clean = "Hello, this is JD's assistant. " + clean
    return clean, pass_message


@router.get("/api/whatsapp/pass-messages")
async def get_pass_messages(request: Request, user: User = Depends(get_current_user)):
    db = request.app.state.SessionLocal()
    try:
        events = db.query(AuditEvent).filter(
            AuditEvent.user_id == user.id,
            AuditEvent.action == "whatsapp.pass_message"
        ).order_by(AuditEvent.created_at.desc()).limit(50).all()
        return {"messages": [
            {"id": e.id, "detail": json.loads(e.detail_json), "time": str(e.created_at)}
            for e in events
        ]}
    finally:
        db.close()


@router.post("/api/whatsapp/pass-messages/{event_id}/acknowledge")
async def ack_pass_message(event_id: str, request: Request, user: User = Depends(get_current_user)):
    db = request.app.state.SessionLocal()
    try:
        e = db.get(AuditEvent, int(event_id))
        if e:
            detail = json.loads(e.detail_json)
            detail["acknowledged"] = True
            e.detail_json = json.dumps(detail)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.get("/api/whatsapp/status")
async def whatsapp_status(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_status(user.id)


@router.get("/api/whatsapp/qr")
async def whatsapp_qr(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_qr(user.id)


@router.post("/api/whatsapp/send")
async def whatsapp_send(
    payload: WhatsAppSendRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    result = await client.send_message(to=payload.to, phone=payload.phone, text=payload.text, user_id=user.id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/whatsapp/chats")
async def whatsapp_chats(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_chats(user.id)


@router.get("/api/whatsapp/messages/{jid:path}")
async def whatsapp_messages(jid: str, request: Request, limit: int = 20, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_messages(jid, limit=limit, user_id=user.id)


@router.get("/api/whatsapp/contacts")
async def whatsapp_contacts(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_contacts(user.id)


@router.post("/api/whatsapp/logout")
async def whatsapp_logout(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.logout(user.id)


@router.get("/api/whatsapp/auto-reply")
async def get_auto_reply(user: User = Depends(get_current_user)):
    return {"enabled": user.whatsapp_auto_reply}


@router.put("/api/whatsapp/auto-reply")
async def set_auto_reply(
    payload: WhatsAppAutoReplyToggle,
    request: Request,
    user: User = Depends(get_current_user),
):
    db = request.app.state.SessionLocal()
    try:
        db_user = db.get(User, user.id)
        db_user.whatsapp_auto_reply = payload.enabled
        db.commit()
        return {"enabled": db_user.whatsapp_auto_reply}
    finally:
        db.close()


@router.post("/api/whatsapp/webhook")
async def whatsapp_webhook(payload: WhatsAppWebhook, request: Request):
    db = request.app.state.SessionLocal()
    try:
        user_id = payload.user_id
        content = f"[WhatsApp {'group' if payload.is_group else 'DM'} from {payload.sender_name}]: {payload.text}"
        log.info("WhatsApp webhook (user %s): %s", user_id, content[:200])
        db.add(AuditEvent(user_id=user_id, action="whatsapp.message", detail_json=json.dumps({
            "from": payload.from_, "sender_name": payload.sender_name,
            "text": payload.text[:500], "is_group": payload.is_group,
        })))
        db.commit()

        if not user_id:
            return {"ok": True}

        owner = db.get(User, user_id)
        if not owner or not owner.whatsapp_auto_reply:
            return {"ok": True}

        if payload.is_group:
            return {"ok": True, "skipped": "group message - auto-reply only for DMs"}

        if not payload.text or not payload.text.strip():
            return {"ok": True, "skipped": "empty message"}

        asyncio.create_task(_auto_reply(
            request.app.state,
            owner.id,
            payload.from_,
            payload.sender_name,
            payload.text.strip(),
            payload.is_group,
        ))
        return {"ok": True, "auto_reply": "queued"}
    except Exception as e:
        log.error("WhatsApp webhook processing failed: %s", e)
        return {"ok": True}
    finally:
        db.close()


async def _auto_reply(state, user_id: str, from_jid: str, sender_name: str, text: str, is_group: bool):
    lease_token = secrets.token_urlsafe(24)
    lease_acquired = False
    try:
        coordinator = getattr(state, "coordinator", None)
        gemini = getattr(coordinator, "gemini", None) if coordinator else None
        if not gemini:
            log.warning("Auto-reply: no Gemini client available")
            return

        async with _contact_locks(state).hold((user_id, from_jid)):
            snapshot = await _acquire_reply_lease(state, user_id, from_jid, sender_name, lease_token)
            if snapshot is None:
                log.warning("Auto-reply lease unavailable")
                return
            lease_acquired = True
            introduced, history = snapshot
            messages = build_auto_reply_messages(sender_name, text, is_group, introduced, history)
            result = await gemini.chat_with_tools(messages, [])
            reply_text, pass_msg = normalize_auto_reply(
                result.get("text", "") if isinstance(result, dict) else "",
                introduced,
            )

            whatsapp = getattr(state, "whatsapp", None)
            if not whatsapp:
                raise RuntimeError("WhatsApp client unavailable")
            send_result = await whatsapp.send_message(to=from_jid, text=reply_text, user_id=user_id)
            if not (
                isinstance(send_result, dict)
                and send_result.get("ok") is True
                and not send_result.get("error")
            ):
                raise RuntimeError("WhatsApp send failed")

            if not _complete_auto_reply(
                state, user_id, from_jid, sender_name, text, reply_text, pass_msg, lease_token,
            ):
                log.warning("Auto-reply lease was replaced before completion")
                return
            lease_acquired = False
            log.info("Auto-reply sent to %s (%s)", sender_name, from_jid)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        log.error("Auto-reply failed (%s)", type(exc).__name__)
    finally:
        if lease_acquired:
            _release_reply_lease(state, user_id, from_jid, lease_token)
