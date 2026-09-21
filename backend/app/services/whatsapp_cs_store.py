"""Persistence layer for the WhatsApp Customer Service capability.

Single point of access to `whatsapp_cs_*` tables. Uses the project's SQLAlchemy
conventions (token id PKs, `utcnow` timestamps, JSON-as-Text, uniqueness via
`UniqueConstraint`). All privileged decisions (who may assign, reply, edit the
KB) are enforced in the API layer / engine — this module only stores data.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    User,
    WhatsAppCSAccount,
    WhatsAppCSConversation,
    WhatsAppCSCustomer,
    WhatsAppCSKnowledgeEntry,
    WhatsAppCSMessage,
    WhatsAppCSOutbound,
    WhatsAppCSSetting,
    WhatsAppCSWebhookEvent,
    utcnow,
)

# ---------------------------------------------------------------------------
# Serialization helpers (dicts for the API layer / frontend; never secrets)
# ---------------------------------------------------------------------------


def serialize_customer(c: WhatsAppCSCustomer) -> Dict[str, Any]:
    return {
        "id": c.id,
        "wa_id": c.wa_id,
        "profile_name": c.profile_name,
        "language": c.language,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def serialize_message(m: WhatsAppCSMessage) -> Dict[str, Any]:
    media = {}
    try:
        media = json.loads(m.media_json or "{}")
    except (TypeError, ValueError):
        media = {}
    error = {}
    try:
        error = json.loads(m.error_json or "{}")
    except (TypeError, ValueError):
        error = {}
    return {
        "id": m.id,
        "external_message_id": m.external_message_id,
        "conversation_id": m.conversation_id,
        "direction": m.direction,
        "type": m.message_type,
        "body": m.body,
        "media": media,
        "delivery_status": m.delivery_status,
        "error": error,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def serialize_conversation(c: WhatsAppCSConversation, customer: Optional[WhatsAppCSCustomer] = None) -> Dict[str, Any]:
    cust = customer or _load_customer_hint(c)
    return {
        "id": c.id,
        "account_id": c.account_id,
        "customer_id": c.customer_id,
        "customer": serialize_customer(cust) if cust else {"id": c.customer_id, "wa_id": "", "profile_name": "", "language": "", "created_at": None, "updated_at": None},
        "status": c.status,
        "handling_mode": c.handling_mode,
        "assigned_rep_id": c.assigned_rep_id,
        "assigned_rep_name": c.assigned_rep_name,
        "escalation_reason": c.escalation_reason,
        "notes": c.notes,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _load_customer_hint(c: WhatsAppCSConversation) -> Optional[WhatsAppCSCustomer]:
    return None  # caller injects the customer to avoid a second query


def serialize_knowledge_entry(e: WhatsAppCSKnowledgeEntry) -> Dict[str, Any]:
    return {
        "id": e.id,
        "category": e.category,
        "title": e.title,
        "body": e.body,
        "tags": e.tags,
        "is_active": e.is_active,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


class WhatsAppCSStore:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------- account

    def get_account(self) -> Optional[WhatsAppCSAccount]:
        return self.db.scalar(select(WhatsAppCSAccount).order_by(WhatsAppCSAccount.created_at.asc()).limit(1))

    def ensure_account(self) -> WhatsAppCSAccount:
        account = self.get_account()
        if account is None:
            account = WhatsAppCSAccount()
            self.db.add(account)
            self.db.flush()
        return account

    def update_connection(
        self,
        *,
        phone_number_id: Optional[str] = None,
        business_account_id: Optional[str] = None,
        display_name: Optional[str] = None,
        status: Optional[str] = None,
        last_error: str = "",
    ) -> WhatsAppCSAccount:
        account = self.ensure_account()
        if phone_number_id is not None:
            account.phone_number_id = phone_number_id.strip()[:64]
        if business_account_id is not None:
            account.business_account_id = business_account_id.strip()[:64]
        if display_name is not None:
            account.display_name = display_name.strip()[:255]
        if status is not None:
            account.status = status
            if status == "verified":
                account.verified_at = utcnow()
        if last_error:
            account.last_error = last_error[:2000]
        return account

    # ------------------------------------------------------------- settings

    def get_setting(self, account_id: str, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.db.get(WhatsAppCSSetting, (account_id, key))
        return row.value if row is not None else default

    def set_setting(self, account_id: str, key: str, value: str) -> None:
        row = self.db.get(WhatsAppCSSetting, (account_id, key))
        if row is None:
            self.db.add(WhatsAppCSSetting(account_id=account_id, key=key, value=value))
        else:
            row.value = value
            row.updated_at = utcnow()

    def get_ai_settings(self, account_id: str, base_settings) -> Dict[str, Any]:
        """Merge env defaults with per-account DB overrides (no secrets)."""
        env_enabled = bool(getattr(base_settings, "whatsapp_cs_ai_enabled", True))
        env_model = getattr(base_settings, "whatsapp_cs_ai_model", None) or getattr(base_settings, "gemini_model", "")
        env_fallback = getattr(base_settings, "whatsapp_cs_default_fallback", "")
        return {
            "enabled": (self.get_setting(account_id, "ai.enabled") or "true").lower() in ("1", "true", "yes"),
            "provider": self.get_setting(account_id, "ai.provider") or "gemini",
            "model": self.get_setting(account_id, "ai.model") or env_model,
            "max_response_length": int(self.get_setting(account_id, "ai.max_response_length") or "600"),
            "fallback": self.get_setting(account_id, "ai.fallback") or env_fallback,
            "escalation_enabled": (self.get_setting(account_id, "ai.escalation") or "true").lower() in ("1", "true", "yes"),
            "sensitive_escalation": (self.get_setting(account_id, "ai.escalation_sensitive") or "true").lower() in ("1", "true", "yes"),
            "env_enabled": env_enabled,
        }

    # ------------------------------------------------- customer/conversations

    def get_or_create_customer(self, account_id: str, wa_id: str, profile_name: str = "", language: str = "") -> WhatsAppCSCustomer:
        customer = self.db.scalar(
            select(WhatsAppCSCustomer).where(
                WhatsAppCSCustomer.account_id == account_id,
                WhatsAppCSCustomer.wa_id == wa_id,
            )
        )
        if customer is None:
            customer = WhatsAppCSCustomer(
                account_id=account_id,
                wa_id=wa_id,
                profile_name=(profile_name or "").strip()[:255],
                language=(language or "").strip()[:16],
            )
            try:
                with self.db.begin_nested():
                    self.db.add(customer)
                    self.db.flush()
            except IntegrityError:
                customer = self.db.scalar(
                    select(WhatsAppCSCustomer).where(
                        WhatsAppCSCustomer.account_id == account_id,
                        WhatsAppCSCustomer.wa_id == wa_id,
                    )
                )
                if customer is None:
                    raise
        elif profile_name and profile_name != customer.profile_name:
            customer.profile_name = profile_name.strip()[:255]
        return customer

    def get_or_create_conversation(self, account_id: str, customer_id: str, default_mode: str = "ai") -> WhatsAppCSConversation:
        conversation = self.db.scalar(
            select(WhatsAppCSConversation)
            .where(
                WhatsAppCSConversation.account_id == account_id,
                WhatsAppCSConversation.customer_id == customer_id,
                WhatsAppCSConversation.status != "resolved",
            )
            .order_by(WhatsAppCSConversation.last_message_at.desc().nullslast())
            .limit(1)
        )
        if conversation is None:
            conversation = WhatsAppCSConversation(
                account_id=account_id,
                customer_id=customer_id,
                status="open",
                handling_mode=default_mode,
            )
            self.db.add(conversation)
            self.db.flush()
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[WhatsAppCSConversation]:
        return self.db.get(WhatsAppCSConversation, conversation_id)

    def get_customer(self, customer_id: str) -> Optional[WhatsAppCSCustomer]:
        return self.db.get(WhatsAppCSCustomer, customer_id)

    def list_conversations(
        self,
        account_id: str,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 30,
        offset: int = 0,
    ) -> Tuple[List[WhatsAppCSConversation], int, Dict[str, WhatsAppCSCustomer]]:
        stmt = select(WhatsAppCSConversation).where(WhatsAppCSConversation.account_id == account_id)
        if status and status in ("open", "human", "resolved"):
            stmt = stmt.where(WhatsAppCSConversation.status == status)
        if search:
            q = f"%{search.strip().lower()}%"
            stmt = stmt.join(WhatsAppCSCustomer, WhatsAppCSConversation.customer_id == WhatsAppCSCustomer.id).where(
                or_(
                    func.lower(WhatsAppCSCustomer.profile_name).like(q),
                    WhatsAppCSCustomer.wa_id.like(q),
                )
            )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            self.db.scalars(
                stmt.order_by(WhatsAppCSConversation.last_message_at.desc().nullslast())
                .limit(limit)
                .offset(offset)
            )
        )
        customers: Dict[str, WhatsAppCSCustomer] = {}
        for row in rows:
            customers[row.customer_id] = self.db.get(WhatsAppCSCustomer, row.customer_id)
        return rows, total, customers

    def conversation_messages(self, conversation_id: str, limit: int = 200) -> List[WhatsAppCSMessage]:
        return list(
            self.db.scalars(
                select(WhatsAppCSMessage)
                .where(WhatsAppCSMessage.conversation_id == conversation_id)
                .order_by(WhatsAppCSMessage.created_at.asc())
                .limit(limit)
            )
        )

    def has_recent_outgoing_reply(self, conversation_id: str, text: str, window_minutes: int = 2) -> bool:
        """Loop guard: did we already send this exact text recently?

        Guards against echo loops where a message we sent is re-delivered as an
        inbound message (which would otherwise trigger another automatic reply).
        """
        threshold = utcnow() - timedelta(minutes=window_minutes)
        exists = self.db.scalar(
            select(WhatsAppCSMessage.id)
            .where(
                WhatsAppCSMessage.conversation_id == conversation_id,
                WhatsAppCSMessage.direction == "outgoing",
                WhatsAppCSMessage.body == text,
                WhatsAppCSMessage.created_at >= threshold,
            )
            .limit(1)
        )
        return exists is not None

    # ------------------------------------------------------------- messages

    def persist_incoming(
        self,
        account_id: str,
        conversation_id: str,
        *,
        external_message_id: str,
        message_type: str,
        body: str,
        media: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[WhatsAppCSMessage], bool]:
        """Persist an incoming message; returns (message, created).

        ``external_message_id`` is unique, so a redelivered event is a no-op.
        """
        existing = self.db.scalar(
            select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == external_message_id)
        )
        if existing is not None:
            return existing, False
        message = WhatsAppCSMessage(
            account_id=account_id,
            conversation_id=conversation_id,
            external_message_id=external_message_id,
            direction="incoming",
            message_type=message_type,
            body=body,
            media_json=json.dumps(media or {}, default=str)[:8000],
            delivery_status="received",
        )
        try:
            with self.db.begin_nested():
                self.db.add(message)
                self.db.flush()
        except IntegrityError:
            existing = self.db.scalar(
                select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == external_message_id)
            )
            return (existing, False) if existing is not None else (None, False)
        self.db.add(
            WhatsAppCSWebhookEvent(
                account_id=account_id,
                external_id=external_message_id,
                event_type="message",
                payload_json=json.dumps({"message_id": external_message_id, "conversation_id": conversation_id}, default=str)[:8000],
                processed=True,
                processed_at=utcnow(),
            )
        )
        conversation = self.get_conversation(conversation_id)
        if conversation is not None:
            conversation.last_message_at = utcnow()
        return message, True

    def record_outgoing(
        self,
        account: WhatsAppCSAccount,
        conversation: WhatsAppCSConversation,
        *,
        wa_phone: str,
        text: str,
        message_type: str = "text",
        template_json: Optional[Dict[str, Any]] = None,
        idempotency_key: str,
    ) -> Tuple[WhatsAppCSOutbound, WhatsAppCSMessage]:
        outbound = WhatsAppCSOutbound(
            account_id=account.id,
            conversation_id=conversation.id,
            wa_phone=wa_phone,
            message_type=message_type,
            text=text,
            template_json=json.dumps(template_json or {}, default=str),
            idempotency_key=idempotency_key,
            status="pending",
        )
        message = WhatsAppCSMessage(
            account_id=account.id,
            conversation_id=conversation.id,
            direction="outgoing",
            message_type=message_type,
            body=text,
            delivery_status="pending",
            idempotency_key=idempotency_key,
        )
        self.db.add(outbound)
        self.db.add(message)
        self.db.flush()
        return outbound, message

    def outbound_by_message_id(self, whatsapp_message_id: str) -> Optional[WhatsAppCSOutbound]:
        return self.db.scalar(
            select(WhatsAppCSOutbound).where(WhatsAppCSOutbound.whatsapp_message_id == whatsapp_message_id).limit(1)
        )

    def mark_outbound_sent(self, outbound: WhatsAppCSOutbound, whatsapp_message_id: str) -> None:
        now = utcnow()
        outbound.whatsapp_message_id = whatsapp_message_id
        outbound.status = "sent"
        outbound.sent_at = now
        outbound.status_at = now
        message = self.db.scalar(
            select(WhatsAppCSMessage).where(
                WhatsAppCSMessage.direction == "outgoing",
                WhatsAppCSMessage.idempotency_key == outbound.idempotency_key,
            ).limit(1)
        )
        if message is not None:
            message.external_message_id = whatsapp_message_id
            message.delivery_status = "sent"
            message.updated_at = now

    def mark_outbound_failed(self, outbound: WhatsAppCSOutbound, error: str, *, permanent: bool = False) -> None:
        now = utcnow()
        outbound.status = "permanent_failed" if permanent else "failed"
        outbound.retry_count = (outbound.retry_count or 0) + 1
        outbound.last_error = (error or "")[:2000]
        outbound.status_at = now
        message = self.db.scalar(
            select(WhatsAppCSMessage).where(
                WhatsAppCSMessage.direction == "outgoing",
                WhatsAppCSMessage.idempotency_key == outbound.idempotency_key,
            ).limit(1)
        )
        if message is not None:
            message.delivery_status = "failed"
            message.error_json = json.dumps({"error": (error or "")[:2000]}, default=str)
            message.updated_at = now

    def reconcile_delivery(self, whatsapp_message_id: str, status: str, error: str = "") -> bool:
        """Apply a Meta `statuses` update. Returns True if a row was updated."""
        status = status.lower()
        if status not in ("sent", "delivered", "read", "failed"):
            return False
        now = utcnow()
        outbound = self.outbound_by_message_id(whatsapp_message_id)
        updated = False
        if outbound is not None:
            outbound.status = status
            outbound.status_at = now
            if status == "failed":
                outbound.last_error = (error or "")[:2000]
            message = self.db.scalar(
                select(WhatsAppCSMessage).where(
                    WhatsAppCSMessage.direction == "outgoing",
                    WhatsAppCSMessage.idempotency_key == outbound.idempotency_key,
                ).limit(1)
            )
            if message is not None:
                message.delivery_status = status
                if status == "failed":
                    message.error_json = json.dumps({"error": (error or "")[:2000]}, default=str)
                message.updated_at = now
            updated = True
        else:
            # Fall back to the mirror message row keyed by external_message_id.
            message = self.db.scalar(
                select(WhatsAppCSMessage).where(WhatsAppCSMessage.external_message_id == whatsapp_message_id).limit(1)
            )
            if message is not None and message.direction == "outgoing":
                message.delivery_status = status
                if status == "failed":
                    message.error_json = json.dumps({"error": (error or "")[:2000]}, default=str)
                message.updated_at = now
                updated = True
        return updated

    def webhook_event_exists(self, external_id: str) -> bool:
        return self.db.scalar(
            select(WhatsAppCSWebhookEvent.id).where(WhatsAppCSWebhookEvent.external_id == external_id).limit(1)
        ) is not None

    # --------------------------------------------------------------- handover

    def set_handling_mode(self, conversation: WhatsAppCSConversation, mode: str, *, reason: str = "") -> WhatsAppCSConversation:
        conversation.handling_mode = mode
        if mode == "human":
            conversation.status = "human"
            if reason:
                conversation.escalation_reason = reason[:2000]
        conversation.updated_at = utcnow()
        return conversation

    def assign_rep(self, conversation: WhatsAppCSConversation, rep: User) -> None:
        conversation.assigned_rep_id = rep.id
        conversation.assigned_rep_name = rep.email.strip()[:255]
        conversation.handling_mode = "human"
        conversation.status = "human"
        conversation.updated_at = utcnow()

    def unassign_rep(self, conversation: WhatsAppCSConversation) -> None:
        conversation.assigned_rep_id = None
        conversation.assigned_rep_name = ""
        if conversation.handling_mode == "human":
            conversation.handling_mode = "ai"
            conversation.status = "open"
        conversation.updated_at = utcnow()

    def append_note(self, conversation: WhatsAppCSConversation, note: str, author: User) -> None:
        prefix = (conversation.notes or "").strip()
        line = f"[{utcnow().isoformat()} {author.email}] {note.strip()[:2000]}"
        conversation.notes = f"{prefix}\n{line}" if prefix else line
        conversation.updated_at = utcnow()

    def set_status(self, conversation: WhatsAppCSConversation, status: str) -> None:
        conversation.status = status
        conversation.updated_at = utcnow()

    def clear_escalation(self, conversation: WhatsAppCSConversation) -> None:
        conversation.escalation_reason = ""
        conversation.assigned_rep_id = None
        conversation.assigned_rep_name = ""
        conversation.updated_at = utcnow()

    # ------------------------------------------------------------ knowledge base

    def kb_list(
        self,
        account_id: str,
        *,
        search: Optional[str] = None,
        category: Optional[str] = None,
        active_only: bool = False,
        limit: int = 200,
    ) -> List[WhatsAppCSKnowledgeEntry]:
        stmt = select(WhatsAppCSKnowledgeEntry).where(WhatsAppCSKnowledgeEntry.account_id == account_id)
        if active_only:
            stmt = stmt.where(WhatsAppCSKnowledgeEntry.is_active.is_(True))
        if category:
            stmt = stmt.where(WhatsAppCSKnowledgeEntry.category == category)
        if search:
            q = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(WhatsAppCSKnowledgeEntry.title).like(q),
                    func.lower(WhatsAppCSKnowledgeEntry.body).like(q),
                    func.lower(WhatsAppCSKnowledgeEntry.tags).like(q),
                )
            )
        return list(self.db.scalars(stmt.order_by(WhatsAppCSKnowledgeEntry.updated_at.desc()).limit(limit)))

    def kb_get(self, entry_id: str) -> Optional[WhatsAppCSKnowledgeEntry]:
        return self.db.get(WhatsAppCSKnowledgeEntry, entry_id)

    def kb_create(
        self,
        account_id: str,
        *,
        category: str,
        title: str,
        body: str,
        tags: str = "",
        is_active: bool = True,
        created_by: Optional[str] = None,
    ) -> WhatsAppCSKnowledgeEntry:
        entry = WhatsAppCSKnowledgeEntry(
            account_id=account_id,
            category=category.strip()[:30] or "other",
            title=title.strip()[:240],
            body=body.strip(),
            tags=tags.strip()[:2000],
            is_active=is_active,
            created_by=created_by,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def kb_update(
        self,
        entry: WhatsAppCSKnowledgeEntry,
        *,
        category: Optional[str] = None,
        title: Optional[str] = None,
        body: Optional[str] = None,
        tags: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> None:
        if category is not None:
            entry.category = category.strip()[:30] or "other"
        if title is not None:
            entry.title = title.strip()[:240]
        if body is not None:
            entry.body = body.strip()
        if tags is not None:
            entry.tags = tags.strip()[:2000]
        if is_active is not None:
            entry.is_active = is_active
        entry.updated_at = utcnow()

    def kb_delete(self, entry: WhatsAppCSKnowledgeEntry) -> None:
        self.db.delete(entry)

    _TOKEN_RE = re.compile(r"[a-z0-9']+")

    def kb_search(self, account_id: str, query: str, limit: int = 5) -> List[WhatsAppCSKnowledgeEntry]:
        """Lightweight relevance search over active entries (no embeddings).

        Scores title/tags double, body single. Deterministic and dependency-free;
        a vector store can be swapped in later without changing callers.
        """
        tokens = [t for t in self._TOKEN_RE.findall(query.lower()) if len(t) > 1]
        if not tokens:
            return []
        rows = list(
            self.db.scalars(
                select(WhatsAppCSKnowledgeEntry)
                .where(
                    WhatsAppCSKnowledgeEntry.account_id == account_id,
                    WhatsAppCSKnowledgeEntry.is_active.is_(True),
                )
                .limit(2000)
            )
        )
        scored = []
        for entry in rows:
            title = entry.title.lower()
            tags = entry.tags.lower()
            body = entry.body.lower()
            score = 0
            for token in tokens:
                if token in title:
                    score += 2
                if token in tags:
                    score += 2
                if token in body:
                    score += 1
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda pair: (-pair[0], pair[1].updated_at or utcnow()))
        return [entry for _, entry in scored[:limit]]

    # --------------------------------------------------------------- overview

    def overview(self, account_id: str) -> Dict[str, Any]:
        now = utcnow()
        week_ago = now - timedelta(days=7)
        conversation = WhatsAppCSConversation
        outbound = WhatsAppCSOutbound
        message = WhatsAppCSMessage

        def _count(stmt):
            return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        total = _count(select(conversation).where(conversation.account_id == account_id))
        open_count = _count(select(conversation).where(conversation.account_id == account_id, conversation.status == "open"))
        human_count = _count(select(conversation).where(conversation.account_id == account_id, conversation.status == "human"))
        resolved = _count(select(conversation).where(conversation.account_id == account_id, conversation.status == "resolved"))
        ai_handled = _count(select(conversation).where(conversation.account_id == account_id, conversation.handling_mode == "ai"))
        human_handled = _count(select(conversation).where(conversation.account_id == account_id, conversation.handling_mode == "human"))
        new_leads = _count(
            select(WhatsAppCSCustomer).where(
                WhatsAppCSCustomer.account_id == account_id,
                WhatsAppCSCustomer.created_at >= week_ago,
            )
        )
        delivery = {}
        for status_value in ("pending", "sent", "delivered", "read", "failed", "permanent_failed"):
            delivery[status_value] = _count(
                select(outbound).where(outbound.account_id == account_id, outbound.status == status_value)
            )
        recent = list(
            self.db.scalars(
                select(message)
                .where(message.account_id == account_id)
                .order_by(message.created_at.desc())
                .limit(15)
            )
        )
        by_id = {
            m.conversation_id: self.db.get(WhatsAppCSConversation, m.conversation_id)
            for m in recent
        }
        activity = []
        for m in recent:
            conv = by_id[m.conversation_id]
            customer = self.db.get(WhatsAppCSCustomer, conv.customer_id) if conv else None
            activity.append({
                "message": serialize_message(m),
                "conversation_id": m.conversation_id,
                "customer_name": customer.profile_name if customer else "",
                "last_message_at": conv.last_message_at.isoformat() if conv and conv.last_message_at else None,
                "handling_mode": conv.handling_mode if conv else "",
            })
        return {
            "conversations_total": total,
            "active_conversations": open_count + human_count,
            "ai_handled": ai_handled,
            "human_handled": human_handled,
            "unresolved": open_count + human_count,
            "resolved": resolved,
            "new_leads_7d": new_leads,
            "delivery": delivery,
            "recent_activity": activity,
        }