"""HTTP surface for WhatsApp Customer Service (official Meta Cloud API).

- ``GET/POST /api/whatsapp-cs/webhook``  — Meta webhook verification + events.
- ``GET  /api/whatsapp-cs/status``       — any authenticated user (no secrets).
- Everything else is admin-only (``require_admin``) and never exposes the
  access token / app secret / verify token.

The existing per-user WhatsApp bridge endpoints (``/api/whatsapp/*``) are
completely unaffected.
"""
import asyncio
import hmac
import json
import logging
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ..models import User, WhatsAppCSMessage, utcnow
from ..rate_limit import limiter
from ..security import get_current_user, require_admin
from ..services.whatsapp_cs_agent import handover_text
from ..services.whatsapp_cs_cloud import WhatsAppCloudAPIError, WhatsAppCloudClient
from ..services.whatsapp_cs_engine import process_webhook_payload, reply_worker
from ..services.whatsapp_cs_store import (
    WhatsAppCSStore,
    serialize_conversation,
    serialize_knowledge_entry,
    serialize_message,
)

log = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp-cs"])

_KB_CATEGORIES = {
    "company", "product", "faq", "pricing", "shipping", "returns",
    "booking", "troubleshooting", "sales", "policy", "other",
}


def _audit(db, user_id, action: str, detail: Dict[str, Any]) -> None:
    from ..models import AuditEvent

    db.add(AuditEvent(user_id=user_id, action=action, detail_json=json.dumps(detail, default=str)[:4000]))


def connection_payload(settings, account) -> Dict[str, Any]:
    """Derive a connection-status payload. Never returns credentials."""
    has_token = bool(settings.whatsapp_cs_access_token)
    has_secret = bool(settings.whatsapp_cs_app_secret)
    has_verify = bool(settings.whatsapp_cs_verify_token)
    phone = (account.phone_number_id if account and account.phone_number_id else "") or (
        settings.whatsapp_cs_phone_number_id or ""
    )
    baca = (account.business_account_id if account and account.business_account_id else "") or (
        settings.whatsapp_cs_business_account_id or ""
    )
    if not has_token and not phone and not baca:
        status = "not_configured"
    elif not (has_token and phone and baca):
        status = "incomplete"
    elif account and account.status == "failed":
        status = "failed"
    elif (account and account.status == "verified") or (has_secret and has_verify):
        status = "verified"
    else:
        status = "incomplete"
    return {
        "enabled": bool(settings.whatsapp_cs_enabled),
        "status": status,
        "phone_number_id": phone,
        "business_account_id": baca,
        "api_version": settings.whatsapp_cs_api_version,
        "has_access_token": has_token,
        "has_app_secret": has_secret,
        "has_verify_token": has_verify,
        "display_name": account.display_name if account else "",
        "last_error": account.last_error if account else "",
        "verified_at": account.verified_at.isoformat() if account and account.verified_at else None,
        "secrets_in_db": False,
    }


# ---------------------------------------------------------------------------
# Meta webhook (public, signature-protected)
# ---------------------------------------------------------------------------


@router.get("/api/whatsapp-cs/webhook")
async def whatsapp_cs_webhook_verify(
    request: Request,
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    settings = request.app.state.settings
    if hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Invalid hub.mode")
    expected = settings.whatsapp_cs_verify_token or ""
    if not expected or not hmac.compare_digest(expected, hub_verify_token or ""):
        raise HTTPException(status_code=403, detail="Invalid verify token")
    return PlainTextResponse(hub_challenge)


@router.post("/api/whatsapp-cs/webhook")
@limiter.limit("600/minute")
async def whatsapp_cs_webhook(request: Request):
    settings = request.app.state.settings
    app_secret = settings.whatsapp_cs_app_secret
    if not app_secret:
        raise HTTPException(status_code=503, detail="WhatsApp Customer Service webhook is not configured")

    raw = await request.body()
    if not WhatsAppCloudClient.validate_signature(
        raw, request.headers.get("x-hub-signature-256") or "", app_secret
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        log.warning("whatsapp-cs webhook: malformed JSON body")
        return {"ok": True, "ignored": "malformed"}

    summary = process_webhook_payload(request.app.state, payload)
    for message_id in summary.get("new_messages", []):
        asyncio.create_task(reply_worker(request.app.state, message_id))
    result = {
        "ok": True,
        "new_messages": len(summary.get("new_messages", [])),
        "statuses_updated": summary.get("statuses_updated", 0),
    }
    if "ignored" in summary:
        result["ignored"] = summary["ignored"]
    return result


# ---------------------------------------------------------------------------
# Connection status (any authenticated user)
# ---------------------------------------------------------------------------


@router.get("/api/whatsapp-cs/status")
async def whatsapp_cs_status(request: Request, user: User = Depends(get_current_user)):
    db = request.app.state.SessionLocal()
    try:
        store = WhatsAppCSStore(db)
        return connection_payload(request.app.state.settings, store.get_account())
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin helpers
# ---------------------------------------------------------------------------


def _admin_db(request) -> tuple:
    db = request.app.state.SessionLocal()
    store = WhatsAppCSStore(db)
    account = store.get_account()
    if account is None:
        account = store.ensure_account()
        db.flush()
    return db, store, account


# ---------------------------------------------------------------------------
# Admin: overview + conversations
# ---------------------------------------------------------------------------


@router.get("/api/whatsapp-cs/overview")
async def whatsapp_cs_overview(request: Request, user: User = Depends(require_admin)):
    db, store, account = _admin_db(request)
    try:
        return store.overview(account.id)
    finally:
        db.close()


@router.get("/api/whatsapp-cs/conversations")
async def whatsapp_cs_conversations(
    request: Request,
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
):
    db, store, account = _admin_db(request)
    try:
        rows, total, customers = store.list_conversations(
            account.id, status=status, search=search, limit=limit, offset=offset
        )
        return {
            "items": [serialize_conversation(c, customers.get(c.customer_id)) for c in rows],
            "total": total,
        }
    finally:
        db.close()


@router.get("/api/whatsapp-cs/conversations/{conversation_id}")
async def whatsapp_cs_conversation_detail(
    conversation_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        customer = store.get_customer(conv.customer_id)
        messages = [serialize_message(m) for m in store.conversation_messages(conversation_id, limit=500)]
        return {"conversation": serialize_conversation(conv, customer), "messages": messages}
    finally:
        db.close()


class AssignRequest(BaseModel):
    rep_email: str = Field(min_length=3, max_length=320)


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/assign")
async def whatsapp_cs_assign(
    conversation_id: str, payload: AssignRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        rep = db.scalar(
            select(User).where(func.lower(User.email) == payload.rep_email.strip().lower()).limit(1)
        )
        if rep is None:
            raise HTTPException(status_code=404, detail="Representative not found")
        store.assign_rep(conv, rep)
        _audit(db, user.id, "whatsapp_cs.admin.assign", {"conversation_id": conv.id, "rep": rep.email})
        db.commit()
        return serialize_conversation(conv, store.get_customer(conv.customer_id))
    finally:
        db.close()


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/unassign")
async def whatsapp_cs_unassign(
    conversation_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        store.unassign_rep(conv)
        _audit(db, user.id, "whatsapp_cs.admin.unassign", {"conversation_id": conv.id})
        db.commit()
        return serialize_conversation(conv, store.get_customer(conv.customer_id))
    finally:
        db.close()


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/reply")
async def whatsapp_cs_reply(
    conversation_id: str, payload: ReplyRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        customer = store.get_customer(conv.customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        if conv.status == "resolved":
            store.set_status(conv, "open")
        # A manual reply always means a human is driving now.
        conv.handling_mode = "human"
        conv.assigned_rep_id = user.id
        conv.assigned_rep_name = user.email.strip()[:255]
        conv.updated_at = utcnow()

        idem = f"admin-{user.id}-{secrets.token_urlsafe(8)}"
        outbound = store.record_outgoing(
            account, conv, wa_phone=customer.wa_id, text=payload.text, message_type="text", idempotency_key=idem
        )[0]
        db.commit()

        client = getattr(request.app.state, "whatsapp_cs_cloud", None)
        if client is None:
            store.mark_outbound_failed(outbound, "cloud client unavailable", permanent=True)
            db.commit()
            raise HTTPException(status_code=503, detail="WhatsApp Cloud API client is not configured")
        try:
            wamid = await client.send_text(customer.wa_id, payload.text)
        except WhatsAppCloudAPIError as exc:
            store.mark_outbound_failed(outbound, exc.message, permanent=not exc.retryable)
            db.commit()
            log.warning("whatsapp-cs manual reply failed: %s", exc.message[:200])
            raise HTTPException(status_code=502, detail=exc.message)
        store.mark_outbound_sent(outbound, wamid)
        conv.last_message_at = utcnow()
        _audit(db, user.id, "whatsapp_cs.admin.reply", {"conversation_id": conv.id, "wamid": wamid})
        db.commit()
        message = db.scalar(
            select(WhatsAppCSMessage)
            .where(WhatsAppCSMessage.direction == "outgoing", WhatsAppCSMessage.idempotency_key == idem)
            .limit(1)
        )
        return {"ok": True, "message": serialize_message(message) if message else None}
    finally:
        db.close()


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/resume-ai")
async def whatsapp_cs_resume_ai(
    conversation_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        store.set_handling_mode(conv, "ai")
        store.clear_escalation(conv)
        if conv.status in ("human", "resolved"):
            store.set_status(conv, "open")
        _audit(db, user.id, "whatsapp_cs.admin.resume_ai", {"conversation_id": conv.id})
        db.commit()
        return serialize_conversation(conv, store.get_customer(conv.customer_id))
    finally:
        db.close()


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/resolve")
async def whatsapp_cs_resolve(
    conversation_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        store.set_status(conv, "resolved")
        _audit(db, user.id, "whatsapp_cs.admin.resolve", {"conversation_id": conv.id})
        db.commit()
        return serialize_conversation(conv, store.get_customer(conv.customer_id))
    finally:
        db.close()


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/reopen")
async def whatsapp_cs_reopen(
    conversation_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        store.set_status(conv, "open")
        _audit(db, user.id, "whatsapp_cs.admin.reopen", {"conversation_id": conv.id})
        db.commit()
        return serialize_conversation(conv, store.get_customer(conv.customer_id))
    finally:
        db.close()


class NotesRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/api/whatsapp-cs/conversations/{conversation_id}/notes")
async def whatsapp_cs_notes(
    conversation_id: str, payload: NotesRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, _ = _admin_db(request)
    try:
        conv = store.get_conversation(conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        store.append_note(conv, payload.text, user)
        db.commit()
        return {"notes": conv.notes}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin: knowledge base
# ---------------------------------------------------------------------------


@router.get("/api/whatsapp-cs/knowledge")
async def whatsapp_cs_knowledge_list(
    request: Request,
    search: Optional[str] = Query(default=None, max_length=120),
    category: Optional[str] = Query(default=None),
    active_only: bool = False,
    user: User = Depends(require_admin),
):
    db, store, account = _admin_db(request)
    try:
        entries = store.kb_list(account.id, search=search, category=category, active_only=active_only)
        return {"items": [serialize_knowledge_entry(e) for e in entries]}
    finally:
        db.close()


class KnowledgeCreateRequest(BaseModel):
    category: str = Field(default="faq", max_length=30)
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1)
    tags: str = Field(default="", max_length=2000)
    is_active: bool = True


class KnowledgeUpdateRequest(BaseModel):
    category: Optional[str] = Field(default=None, max_length=30)
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    body: Optional[str] = Field(default=None, min_length=1)
    tags: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None


@router.post("/api/whatsapp-cs/knowledge")
async def whatsapp_cs_knowledge_create(
    payload: KnowledgeCreateRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        if payload.category not in _KB_CATEGORIES:
            payload.category = "other"
        entry = store.kb_create(
            account.id,
            category=payload.category,
            title=payload.title,
            body=payload.body,
            tags=payload.tags,
            is_active=payload.is_active,
            created_by=user.id,
        )
        _audit(db, user.id, "whatsapp_cs.admin.kb_create", {"kb_id": entry.id})
        db.commit()
        return serialize_knowledge_entry(entry)
    finally:
        db.close()


@router.put("/api/whatsapp-cs/knowledge/{entry_id}")
async def whatsapp_cs_knowledge_update(
    entry_id: str, payload: KnowledgeUpdateRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        entry = store.kb_get(entry_id)
        if entry is None or entry.account_id != account.id:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")
        category = payload.category
        if category is not None and category not in _KB_CATEGORIES:
            category = "other"
        store.kb_update(
            entry,
            category=category,
            title=payload.title,
            body=payload.body,
            tags=payload.tags,
            is_active=payload.is_active,
        )
        _audit(db, user.id, "whatsapp_cs.admin.kb_update", {"kb_id": entry.id})
        db.commit()
        return serialize_knowledge_entry(entry)
    finally:
        db.close()


@router.post("/api/whatsapp-cs/knowledge/{entry_id}/toggle")
async def whatsapp_cs_knowledge_toggle(
    entry_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        entry = store.kb_get(entry_id)
        if entry is None or entry.account_id != account.id:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")
        entry.is_active = not entry.is_active
        _audit(db, user.id, "whatsapp_cs.admin.kb_toggle", {"kb_id": entry.id, "active": entry.is_active})
        db.commit()
        return serialize_knowledge_entry(entry)
    finally:
        db.close()


@router.delete("/api/whatsapp-cs/knowledge/{entry_id}")
async def whatsapp_cs_knowledge_delete(
    entry_id: str, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        entry = store.kb_get(entry_id)
        if entry is None or entry.account_id != account.id:
            raise HTTPException(status_code=404, detail="Knowledge entry not found")
        store.kb_delete(entry)
        _audit(db, user.id, "whatsapp_cs.admin.kb_delete", {"kb_id": entry_id})
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin: AI settings + connection
# ---------------------------------------------------------------------------


class AiSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    provider: Optional[str] = Field(default=None, max_length=20)
    model: Optional[str] = Field(default=None, max_length=120)
    max_response_length: Optional[int] = Field(default=None, ge=60, le=2000)
    fallback: Optional[str] = Field(default=None, max_length=1000)
    escalation_enabled: Optional[bool] = None
    sensitive_escalation: Optional[bool] = None


@router.get("/api/whatsapp-cs/ai-settings")
async def whatsapp_cs_ai_settings_get(request: Request, user: User = Depends(require_admin)):
    db, store, account = _admin_db(request)
    try:
        return store.get_ai_settings(account.id, request.app.state.settings)
    finally:
        db.close()


@router.put("/api/whatsapp-cs/ai-settings")
async def whatsapp_cs_ai_settings_put(
    payload: AiSettingsRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        if payload.provider is not None and payload.provider not in ("gemini", "none"):
            raise HTTPException(status_code=422, detail="provider must be 'gemini' or 'none'")
        updates = {
            "ai.enabled": str(bool(payload.enabled)).lower() if payload.enabled is not None else None,
            "ai.provider": payload.provider,
            "ai.model": payload.model.strip() if payload.model is not None else None,
            "ai.max_response_length": str(payload.max_response_length) if payload.max_response_length is not None else None,
            "ai.fallback": payload.fallback.strip() if payload.fallback is not None else None,
            "ai.escalation": str(bool(payload.escalation_enabled)).lower() if payload.escalation_enabled is not None else None,
            "ai.escalation_sensitive": str(bool(payload.sensitive_escalation)).lower() if payload.sensitive_escalation is not None else None,
        }
        for key, value in updates.items():
            if value is not None:
                store.set_setting(account.id, key, value)
        db.commit()
        return store.get_ai_settings(account.id, request.app.state.settings)
    finally:
        db.close()


class ConnectionUpdateRequest(BaseModel):
    phone_number_id: Optional[str] = Field(default=None, max_length=64)
    business_account_id: Optional[str] = Field(default=None, max_length=64)
    display_name: Optional[str] = Field(default=None, max_length=255)


@router.get("/api/whatsapp-cs/connection")
async def whatsapp_cs_connection_get(request: Request, user: User = Depends(require_admin)):
    db, store, _ = _admin_db(request)
    try:
        return connection_payload(request.app.state.settings, store.get_account())
    finally:
        db.close()


@router.put("/api/whatsapp-cs/connection")
async def whatsapp_cs_connection_update(
    payload: ConnectionUpdateRequest, request: Request, user: User = Depends(require_admin)
):
    db, store, account = _admin_db(request)
    try:
        settings = request.app.state.settings
        store.update_connection(
            phone_number_id=payload.phone_number_id,
            business_account_id=payload.business_account_id,
            display_name=payload.display_name,
        )
        # Recompute status from actual configuration (token presence is required).
        has_token = bool(settings.whatsapp_cs_access_token)
        phone = account.phone_number_id or (settings.whatsapp_cs_phone_number_id or "")
        baca = account.business_account_id or (settings.whatsapp_cs_business_account_id or "")
        if has_token and phone and baca:
            store.update_connection(status="verified")
        elif has_token or phone or baca:
            store.update_connection(status="incomplete")
        else:
            store.update_connection(status="not_configured")
        _audit(db, user.id, "whatsapp_cs.admin.connection_update", {
            "phone_number_id": bool(phone), "business_account_id": bool(baca),
        })
        db.commit()
        client = getattr(request.app.state, "whatsapp_cs_cloud", None)
        if client is not None:
            client.phone_number_id = account.phone_number_id or settings.whatsapp_cs_phone_number_id
        return connection_payload(settings, store.get_account())
    finally:
        db.close()