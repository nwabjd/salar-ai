import json
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import WhatsAppContactState


class WhatsAppConversationStore:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, user_id: str, contact_jid: str, sender_name: str) -> WhatsAppContactState:
        state = self.db.scalar(select(WhatsAppContactState).where(
            WhatsAppContactState.user_id == user_id,
            WhatsAppContactState.contact_jid == contact_jid,
        ))
        if state is None:
            state = WhatsAppContactState(
                user_id=user_id,
                contact_jid=contact_jid,
                sender_name=(sender_name or "").strip()[:255],
            )
            try:
                with self.db.begin_nested():
                    self.db.add(state)
                    self.db.flush()
            except IntegrityError:
                state = self.db.scalar(select(WhatsAppContactState).where(
                    WhatsAppContactState.user_id == user_id,
                    WhatsAppContactState.contact_jid == contact_jid,
                ))
                if state is None:
                    raise
        elif sender_name:
            state.sender_name = sender_name.strip()[:255]
        return state

    @staticmethod
    def history(state: WhatsAppContactState) -> List[Dict[str, str]]:
        try:
            value = json.loads(state.history_json or "[]")
        except (TypeError, ValueError):
            return []
        if not isinstance(value, list):
            return []

        turns = []
        for item in value:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            text = item.get("text")
            if role not in {"sender", "assistant"} or not isinstance(text, str):
                continue
            normalized = " ".join(text.split())
            if normalized:
                turns.append({"role": role, "text": normalized[:1000]})
        return turns[-8:]

    def record_exchange(
        self,
        state: WhatsAppContactState,
        incoming: str,
        reply: str,
        introduced: bool,
    ) -> None:
        turns = self.history(state)
        incoming_text = " ".join((incoming or "").split())[:1000]
        reply_text = " ".join((reply or "").split())[:1000]
        turns.extend([
            {"role": "sender", "text": incoming_text},
            {"role": "assistant", "text": reply_text},
        ])
        state.history_json = json.dumps(turns[-8:])
        state.introduced = bool(state.introduced or introduced)
        state.active_topic = incoming_text[:500]
        self.db.flush()
