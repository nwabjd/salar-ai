# backend/app/services/world_model/memory_sync.py
"""MemorySyncService — unify the fragmented memory stores into the world graph.

SALAR has historically kept separate stores for the same underlying reality:
the `Memory`/`MemoryRelation` graph, `MediaMemory`, `KnowledgeDocument`, and the
`IntelEvent` ledger. This service mirrors each store into the WorldGraph so that
a project, person, file, or event appears once with provenance from all stores,
and so the SituationEngine can reason over a single, connected world.

Every sync method is idempotent: repeated runs merge into the same nodes.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ...models import (
    IntelEvent,
    KnowledgeDocument,
    MediaMemory,
    Memory,
    MemoryRelation,
)
from .graph import WorldGraph

log = logging.getLogger(__name__)

# Memory.kind -> world graph entity_type. Everything else maps to "memory".
_KIND_ENTITY_TYPE = {
    "person": "person",
    "project": "project",
    "file": "file",
    "event": "event",
    "preference": "preference",
    "decision": "decision",
    "place": "place",
}


class MemorySyncService:
    def __init__(self, db) -> None:
        self.graph = WorldGraph(db)
        self.db = db

    # ---------------- public entry point ----------------

    def sync_all(self, user_id: str) -> Dict[str, int]:
        counts = {
            "memories": self.sync_memories(user_id),
            "media": self.sync_media(user_id),
            "knowledge": self.sync_knowledge(user_id),
            "intel": self.sync_intel(user_id),
        }
        return counts

    # ---------------- per-store mirrors ----------------

    def sync_memories(self, user_id: str) -> int:
        memories = self.db.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
        ).all()
        count = 0
        for memory in memories:
            entity = self._mirror_memory(user_id, memory)
            if entity is not None:
                count += 1
        self.db.flush()
        return count

    def sync_media(self, user_id: str) -> int:
        rows = self.db.scalars(
            select(MediaMemory).where(MediaMemory.user_id == user_id).order_by(MediaMemory.created_at.desc())
        ).all()
        count = 0
        for row in rows:
            entity_type = _media_entity_type(row.kind)
            self.graph.upsert_entity(
                user_id, entity_type, f"media:{row.id}",
                name=row.caption[:160] or row.kind or "media",
                summary=(row.transcript or row.caption or "")[:800],
                props={"kind": row.kind, "storage_path": row.storage_path},
                source="media_memory",
            )
            count += 1
        self.db.flush()
        return count

    def sync_knowledge(self, user_id: str) -> int:
        docs = self.db.scalars(
            select(KnowledgeDocument).where(KnowledgeDocument.user_id == user_id, KnowledgeDocument.status == "ready")
        ).all()
        count = 0
        for doc in docs:
            self.graph.upsert_entity(
                user_id, "document", f"document:{doc.id}",
                name=doc.filename,
                summary=(doc.full_text or "")[:500],
                props={"content_type": doc.content_type, "chunk_count": doc.chunk_count},
                source="knowledge",
            )
            count += 1
        self.db.flush()
        return count

    def sync_intel(self, user_id: str) -> int:
        events = self.db.scalars(
            select(IntelEvent).where(IntelEvent.user_id == user_id).order_by(IntelEvent.created_at.desc()).limit(500)
        ).all()
        count = 0
        for event in events:
            self.graph.upsert_entity(
                user_id, "intel", f"intel:{event.id}",
                name=event.title[:200],
                summary=event.summary[:800] or event.title,
                props={
                    "kind": event.kind,
                    "severity": event.severity,
                    "source": event.source,
                    "is_read": event.is_read,
                },
                source=event.source or "intel",
            )
            count += 1
        self.db.flush()
        return count

    def sync_relations(self, user_id: str) -> int:
        """Mirror MemoryRelation edges into world relations (runs after sync_memories)."""
        rows = self.db.scalars(
            select(MemoryRelation).where(MemoryRelation.user_id == user_id)
        ).all()
        count = 0
        for row in rows:
            src = self._resolve_memory_entity(user_id, row.from_memory_id)
            dst = self._resolve_memory_entity(user_id, row.to_memory_id)
            if src is None or dst is None:
                continue
            self.graph.relate_by_entity_ids(
                user_id, src.id, dst.id, row.relation, source="memory_graph"
            )
            count += 1
        self.db.flush()
        return count

    # ---------------- helpers ----------------

    def _mirror_memory(self, user_id: str, memory: Memory):
        entity_type = _KIND_ENTITY_TYPE.get(memory.kind, "memory")
        entity = self.graph.upsert_entity(
            user_id, entity_type, memory.title.strip().lower() or f"memory:{memory.id}",
            name=memory.title,
            summary=memory.content[:800],
            props={
                "kind": memory.kind,
                "layer": memory.layer,
                "memory_id": memory.id,
                "tags": _loads(memory.tags_json),
            },
            source="memory_graph",
        )
        return entity

    def _resolve_memory_entity(self, user_id: str, memory_id: str):
        """Find the world entity that mirrors a Memory record (via props.memory_id)."""
        candidates = self.graph.search(user_id, memory_id, limit=10)
        for entity in candidates:
            if entity.props.get("memory_id") == memory_id:
                return entity
        memory = self.db.get(Memory, memory_id)
        if memory is None or memory.user_id != user_id:
            return None
        return self.graph._resolve(user_id, _KIND_ENTITY_TYPE.get(memory.kind, "memory"), memory.title.strip().lower())


def _media_entity_type(kind: str) -> str:
    if kind == "image":
        return "image"
    if kind == "audio":
        return "audio"
    if kind == "video":
        return "video"
    return "media"


def _loads(text: str) -> Any:
    try:
        return json.loads(text or "[]")
    except Exception:
        return []
