import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..models import AuditEvent, User
from ..security import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])


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


def build_auto_reply_messages(sender_name: str, text: str, is_group: bool):
    context = f"WhatsApp {'group' if is_group else 'DM'} message from {sender_name}: {text}"
    policy = (
        "You are JD's assistant, replying professionally to a WhatsApp sender on JD's behalf. "
        "Never pretend to be JD and never introduce yourself as an AI. When a conversation begins with a greeting "
        "or no clear request, introduce yourself briefly as JD's assistant and ask what query you can help with. "
        "When the sender gives a specific query, address it directly and helpfully using reliable information. "
        "If essential details are missing, acknowledge the request and ask a focused follow-up question. "
        "Do not fabricate facts, promises, availability, prices, dates, or actions. Do not use blunt refusal phrases "
        "such as 'I will not' or 'I cannot'; explain the limitation briefly and offer the most useful next step. "
        "Use a warm, authentic, professional tone in one to three short sentences with plain text only. "
        "If the sender asks to speak with JD, offer to help first and ask for the purpose or key details. "
        "If the sender explicitly asks you to tell JD something or pass a message, respond only with "
        "GOTOPASS: followed by the exact concise message for JD. Use GOTOPASS only for explicit pass-message requests."
    )
    return [{"role": "system", "content": policy}, {"role": "user", "content": context}]


def normalize_auto_reply(reply_text: str):
    clean = (reply_text or "").strip()
    if not clean:
        return "Hello, this is JD’s assistant. How may I help you today?", None
    if clean.startswith("GOTOPASS:"):
        message = clean[len("GOTOPASS:"):].strip()
        return "Thank you. I’ll make sure JD receives your message. Is there anything else I can help you with?", message or None
    return clean, None


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
    try:
        coordinator = getattr(state, "coordinator", None)
        gemini = getattr(coordinator, "gemini", None) if coordinator else None
        if not gemini:
            log.warning("Auto-reply: no Gemini client available")
            return

        messages = build_auto_reply_messages(sender_name, text, is_group)

        result = await gemini.chat_with_tools(messages, [])
        reply_text = result.get("text", "").strip()
        reply_text, pass_msg = normalize_auto_reply(reply_text)

        whatsapp = getattr(state, "whatsapp", None)
        if whatsapp:
            await whatsapp.send_message(to=from_jid, text=reply_text, user_id=user_id)
            log.info("Auto-reply sent to %s (%s): %s", sender_name, from_jid, reply_text[:100])

            save_db = state.SessionLocal()
            try:
                save_db.add(AuditEvent(
                    user_id=user_id,
                    action="whatsapp.auto_reply",
                    detail_json=json.dumps({
                        "to": from_jid, "sender_name": sender_name,
                        "incoming": text[:300], "reply": reply_text[:300],
                    }),
                ))
                if pass_msg:
                    save_db.add(AuditEvent(
                        user_id=user_id,
                        action="whatsapp.pass_message",
                        detail_json=json.dumps({
                            "from": from_jid, "sender_name": sender_name,
                            "message": pass_msg[:500], "acknowledged": False,
                        }),
                    ))
                save_db.commit()
            finally:
                save_db.close()
    except Exception as e:
        log.error("Auto-reply failed: %s", e, exc_info=True)
