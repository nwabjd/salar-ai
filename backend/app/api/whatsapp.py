import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..database import get_db
from ..models import AuditEvent, Conversation, Message, User
from ..schemas import ChatRequest
from ..security import get_current_user

log = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])


class WhatsAppSendRequest(BaseModel):
    to: Optional[str] = None
    phone: Optional[str] = None
    text: str


class WhatsAppWebhook(BaseModel):
    from_: str = Field(alias="from")
    sender_name: str
    text: str
    is_group: bool = False
    timestamp: int = 0


class WhatsAppAutoReplyToggle(BaseModel):
    enabled: bool


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
    return await client.get_status()


@router.get("/api/whatsapp/qr")
async def whatsapp_qr(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    qr = await client.get_qr()
    return {"qr": qr}


@router.post("/api/whatsapp/send")
async def whatsapp_send(
    payload: WhatsAppSendRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    result = await client.send_message(to=payload.to, phone=payload.phone, text=payload.text)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/whatsapp/chats")
async def whatsapp_chats(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_chats()


@router.get("/api/whatsapp/messages/{jid:path}")
async def whatsapp_messages(jid: str, request: Request, limit: int = 20, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_messages(jid, limit=limit)


@router.get("/api/whatsapp/contacts")
async def whatsapp_contacts(request: Request, user: User = Depends(get_current_user)):
    client = getattr(request.app.state, "whatsapp", None)
    if not client:
        raise HTTPException(status_code=503, detail="WhatsApp bridge not configured")
    return await client.get_contacts()


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
        content = f"[WhatsApp {'group' if payload.is_group else 'DM'} from {payload.sender_name}]: {payload.text}"
        log.info("WhatsApp webhook: %s", content[:200])
        db.add(AuditEvent(user_id=None, action="whatsapp.message", detail_json=json.dumps({
            "from": payload.from_, "sender_name": payload.sender_name,
            "text": payload.text[:500], "is_group": payload.is_group,
        })))
        db.commit()

        admin = db.scalar(select(User).where(User.is_admin == True).limit(1))
        if not admin or not admin.whatsapp_auto_reply:
            return {"ok": True}

        if not payload.text or not payload.text.strip():
            return {"ok": True, "skipped": "empty message"}

        asyncio.create_task(_auto_reply(
            request.app.state,
            admin.id,
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

        context = f"WhatsApp {'group' if is_group else 'DM'} message from {sender_name}: {text}"
        messages = [
            {"role": "system", "content": (
                f"You are SALAR, JD's personal AI assistant. You are replying to a WhatsApp message on behalf of JD. "
                f"Never introduce yourself as an AI or say you are an artificial intelligence. "
                f"You speak naturally like a helpful human assistant who works for JD. "
                f"Reply in 1-2 short natural sentences. Be helpful, friendly, and concise. "
                f"Do not use markdown, bullet points, or formatting — just plain text. "
                f"If the message is a question, answer it. If it's a greeting, greet back warmly. "
                f"If someone asks to talk to JD, say JD is unavailable and ask if you can help. "
                f"If someone asks you to pass a message, relay info, or tell JD something, "
                f"respond with: GOTOPASS: <the message they want passed>. "
                f"Only use GOTOPASS when someone explicitly asks you to tell JD something or pass a message. "
                f"Keep it brief and personal, like a real person responding."
            )},
            {"role": "user", "content": context},
        ]

        result = await gemini.chat_with_tools(messages, [])
        reply_text = result.get("text", "").strip()
        if not reply_text:
            reply_text = "Thanks for your message! I'll get back to you soon."

        # Detect pass-along messages
        pass_msg = None
        if reply_text.startswith("GOTOPASS:"):
            pass_msg = reply_text[len("GOTOPASS:"):].strip()
            reply_text = f"Got it, I'll make sure JD gets that message!"

        whatsapp = getattr(state, "whatsapp", None)
        if whatsapp:
            await whatsapp.send_message(to=from_jid, text=reply_text)
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
