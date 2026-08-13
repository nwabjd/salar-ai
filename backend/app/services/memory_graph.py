# backend/app/services/memory_graph.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select

from ..models import Memory, MemoryRelation, token_id, utcnow

log = logging.getLogger(__name__)

MEMORY_KINDS = {"person", "project", "file", "preference", "decision", "place", "event", "memory"}


class MemoryGraph:
    def __init__(self, db) -> None:
        self.db = db

    def tags(self, memory: Memory) -> list:
        try:
            return json.loads(memory.tags_json or "[]")
        except Exception:
            return []

    def connect(self, user_id: str, from_memory_id: str, to_memory_id: str, relation: str = "related") -> MemoryRelation:
        if from_memory_id == to_memory_id:
            raise ValueError("cannot connect memory to itself")
        if relation not in self._valid_relations():
            raise ValueError(f"invalid relation: {relation}")
        existing = self.db.scalar(
            select(MemoryRelation).where(
                MemoryRelation.user_id == user_id,
                MemoryRelation.from_memory_id == from_memory_id,
                MemoryRelation.to_memory_id == to_memory_id,
            )
        )
        if existing:
            existing.relation = relation
            return existing
        rel = MemoryRelation(
            id=token_id(), user_id=user_id,
            from_memory_id=from_memory_id, to_memory_id=to_memory_id,
            relation=relation, created_at=utcnow(),
        )
        self.db.add(rel)
        return rel

    def disconnect(self, user_id: str, relation_id: str) -> bool:
        rel = self.db.get(MemoryRelation, relation_id)
        if rel is None or rel.user_id != user_id:
            return False
        self.db.delete(rel)
        return True

    def neighbors(self, user_id: str, memory_id: str, *, relation: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        base = (
            select(Memory)
            .join(MemoryRelation, or_(
                (MemoryRelation.from_memory_id == Memory.id) & (MemoryRelation.to_memory_id == memory_id),
                (MemoryRelation.to_memory_id == Memory.id) & (MemoryRelation.from_memory_id == memory_id),
            ))
            .where(MemoryRelation.user_id == user_id, Memory.id != memory_id)
        )
        if relation:
            base = base.where(MemoryRelation.relation == relation)
        rows = self.db.scalars(base.order_by(Memory.updated_at.desc()).limit(limit)).all()
        return [self._node(m) for m in rows]

    def graph(self, user_id: str, *, limit_nodes: int = 200) -> Dict[str, Any]:
        memories = self.db.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc()).limit(limit_nodes)
        ).all()
        node_ids = {m.id for m in memories}
        rels = self.db.scalars(
            select(MemoryRelation).where(
                MemoryRelation.user_id == user_id,
                MemoryRelation.from_memory_id.in_(node_ids),
                MemoryRelation.to_memory_id.in_(node_ids),
            )
        ).all()
        return {
            "nodes": [self._node(m) for m in memories],
            "edges": [
                {"id": r.id, "from": r.from_memory_id, "to": r.to_memory_id, "relation": r.relation}
                for r in rels
            ],
        }

    def memories_by_kind(self, user_id: str, kind: str, *, limit: int = 100) -> List[Dict[str, Any]]:
        if kind not in MEMORY_KINDS:
            raise ValueError(f"invalid kind: {kind}")
        memories = self.db.scalars(
            select(Memory).where(Memory.user_id == user_id, Memory.kind == kind).order_by(Memory.updated_at.desc()).limit(limit)
        ).all()
        return [self._node(m) for m in memories]

    def _node(self, m: Memory) -> Dict[str, Any]:
        return {
            "id": m.id,
            "kind": m.kind,
            "layer": m.layer,
            "title": m.title,
            "tags": self.tags(m),
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }

    @staticmethod
    def _valid_relations() -> set:
        return {
            "related", "person", "project", "file", "place", "event",
            "created_by", "contains", "mentioned_in", "belongs_to", "scheduled_for", "caused_by",
        }
