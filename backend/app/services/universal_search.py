# backend/app/services/universal_search.py
import logging
from typing import Any, Dict, List

from sqlalchemy import or_, select

from ..models import (
    Conversation, Document, KnowledgeChunk, Memory, Message,
    Mission, Project, Reminder, Task,
)

log = logging.getLogger(__name__)

SEARCHABLE_SOURCES = [
    "files", "documents", "conversations", "messages", "memory",
    "knowledge", "tasks", "reminders", "projects", "missions",
]


class UniversalSearch:
    def __init__(self, db) -> None:
        self.db = db

    def _like(self, *fields, q: str):
        pattern = f"%{q}%"
        return [field.ilike(pattern) for field in fields]

    def search(self, user_id: str, query: str, *, sources: List[str] = None, limit_per_source: int = 5) -> List[Dict[str, Any]]:
        q = query.strip()
        if not q:
            return []
        selected = sources or SEARCHABLE_SOURCES
        results: List[Dict[str, Any]] = []
        add = results.append
        if "projects" in selected:
            rows = self.db.scalars(select(Project).where(Project.user_id == user_id, or_(*self._like(Project.name, Project.description, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "project", "id": r.id, "title": r.name, "snippet": r.description, "meta": {"kind": r.name[:40]}})
        if "conversations" in selected:
            rows = self.db.scalars(select(Conversation).where(Conversation.user_id == user_id, Conversation.title.ilike(f"%{q}%")).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "conversation", "id": r.id, "title": r.title, "snippet": "", "meta": {}})
        if "messages" in selected:
            rows = self.db.scalars(select(Message).join(Conversation, Conversation.id == Message.conversation_id).where(Conversation.user_id == user_id, Message.content.ilike(f"%{q}%")).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "message", "id": r.id, "title": f"{r.role} message", "snippet": r.content[:200], "meta": {"conversation_id": r.conversation_id}})
        if "memory" in selected:
            rows = self.db.scalars(select(Memory).where(Memory.user_id == user_id, or_(*self._like(Memory.title, Memory.content, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "memory", "id": r.id, "title": r.title, "snippet": r.content[:200], "meta": {"layer": r.layer, "kind": r.kind}})
        if "knowledge" in selected:
            rows = self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id, KnowledgeChunk.content.ilike(f"%{q}%")).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "knowledge", "id": r.id, "title": "knowledge snippet", "snippet": r.content[:200], "meta": {"document_id": r.document_id}})
        if "documents" in selected or "files" in selected:
            rows = self.db.scalars(select(Document).where(Document.user_id == user_id, or_(*self._like(Document.filename, Document.extracted_text, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "document", "id": r.id, "title": r.filename, "snippet": (r.extracted_text or "")[:200], "meta": {"media_type": r.media_type}})
        if "tasks" in selected:
            rows = self.db.scalars(select(Task).where(Task.user_id == user_id, or_(*self._like(Task.title, Task.description, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "task", "id": r.id, "title": r.title, "snippet": r.description, "meta": {"status": r.status, "priority": r.priority}})
        if "reminders" in selected:
            rows = self.db.scalars(select(Reminder).where(Reminder.user_id == user_id, or_(*self._like(Reminder.title, Reminder.message, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "reminder", "id": r.id, "title": r.title, "snippet": r.message, "meta": {"is_done": r.is_done}})
        if "missions" in selected:
            rows = self.db.scalars(select(Mission).where(Mission.user_id == user_id, or_(*self._like(Mission.goal, Mission.result_summary, q=q))).limit(limit_per_source)).all()
            for r in rows:
                add({"type": "mission", "id": r.id, "title": r.goal[:120], "snippet": (r.result_summary or "")[:200], "meta": {"status": r.status}})
        return results
