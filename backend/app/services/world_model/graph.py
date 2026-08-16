# backend/app/services/world_model/graph.py
"""WorldGraph — the continuously-updated world model graph.

Entities are deduplicated by (user, entity_type, canonical key) and carry
provenance (source, first/last seen, confidence). Relations are typed,
weighted edges between entities. Both can carry a TTL so stale facts decay
out of the model when they are no longer observed.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, select

from ...models import WorldEntity, WorldRelation, WorldObservation, utcnow

log = logging.getLogger(__name__)

KEYWORD_RE = re.compile(r"[a-z0-9._-]+")


def canonical(entity_type: str, key: str) -> str:
    """Build a stable, normalized canonical key from a type and raw key."""
    if not key:
        return ""
    return f"{entity_type}:{key.strip().lower()}"


def _norm_key(key: str) -> str:
    return key.strip().lower()


class WorldGraph:
    def __init__(self, db) -> None:
        self.db = db

    # ---------------- entities ----------------

    def upsert_entity(
        self,
        user_id: str,
        entity_type: str,
        key: str,
        *,
        name: str = "",
        summary: str = "",
        props: Optional[Dict[str, Any]] = None,
        source: str = "",
        confidence: float = 1.0,
        ttl_seconds: Optional[int] = None,
    ) -> WorldEntity:
        if not entity_type or not key:
            raise ValueError("entity_type and key are required")
        key = key.strip().lower()
        now = utcnow()
        entity = self.db.scalar(
            select(WorldEntity).where(
                WorldEntity.user_id == user_id,
                WorldEntity.entity_type == entity_type,
                WorldEntity.key == key,
            )
        )
        if entity is None:
            entity = WorldEntity(
                id=token_id(),
                user_id=user_id,
                entity_type=entity_type,
                key=key,
                name=name,
                summary=summary,
                props_json=json.dumps(props or {}, default=str),
                source=source,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                ttl_seconds=ttl_seconds,
            )
            self.db.add(entity)
            self.db.flush()
        else:
            if name:
                entity.name = name
            if summary:
                entity.summary = summary
            if props:
                merged = dict(entity.props)
                merged.update(props)
                entity.props_json = json.dumps(merged, default=str)
            entity.confidence = max(entity.confidence, confidence)
            entity.last_seen = now
            if ttl_seconds is not None:
                entity.ttl_seconds = ttl_seconds
        return entity

    def touch(self, user_id: str, entity_type: str, key: str, *, source: str = "") -> Optional[WorldEntity]:
        entity = self.db.scalar(
            select(WorldEntity).where(
                WorldEntity.user_id == user_id,
                WorldEntity.entity_type == entity_type,
                WorldEntity.key == _norm_key(key),
            )
        )
        if entity is None:
            return None
        entity.last_seen = utcnow()
        if source:
            entity.source = source
        return entity

    def _resolve(self, user_id: str, entity_type: str, key: str) -> Optional[WorldEntity]:
        return self.db.scalar(
            select(WorldEntity).where(
                WorldEntity.user_id == user_id,
                WorldEntity.entity_type == entity_type,
                WorldEntity.key == _norm_key(key),
            )
        )

    def entity_by_id(self, user_id: str, entity_id: str) -> Optional[WorldEntity]:
        return self.db.scalar(
            select(WorldEntity).where(WorldEntity.id == entity_id, WorldEntity.user_id == user_id)
        )

    def entities(self, user_id: str, *, entity_type: Optional[str] = None, limit: int = 200) -> List[WorldEntity]:
        q = select(WorldEntity).where(WorldEntity.user_id == user_id)
        if entity_type:
            q = q.where(WorldEntity.entity_type == entity_type)
        return list(self.db.scalars(q.order_by(WorldEntity.last_seen.desc()).limit(limit)))

    def search(self, user_id: str, query: str, *, limit: int = 25) -> List[WorldEntity]:
        tokens = KEYWORD_RE.findall(query.lower())
        if not tokens:
            return []
        q = select(WorldEntity).where(WorldEntity.user_id == user_id)
        clauses = [
            WorldEntity.name.ilike(f"%{t}%")
            | WorldEntity.key.ilike(f"%{t}%")
            | WorldEntity.summary.ilike(f"%{t}%")
            for t in tokens
        ]
        q = q.where(or_(*clauses))
        return list(self.db.scalars(q.order_by(WorldEntity.last_seen.desc()).limit(limit)))

    # ---------------- relations ----------------

    def relate(
        self,
        user_id: str,
        from_type: str,
        from_key: str,
        relation: str,
        to_type: str,
        to_key: str,
        *,
        source: str = "",
        weight: float = 1.0,
        ttl_seconds: Optional[int] = None,
        auto_create: bool = True,
    ) -> Optional[WorldRelation]:
        src = self._resolve(user_id, from_type, from_key)
        dst = self._resolve(user_id, to_type, to_key)
        if src is None or dst is None:
            if not auto_create:
                return None
            src = src or self.upsert_entity(user_id, from_type, from_key, source=source)
            dst = dst or self.upsert_entity(user_id, to_type, to_key, source=source)
        return self.relate_by_entity_ids(
            user_id, src.id, dst.id, relation,
            source=source, weight=weight, ttl_seconds=ttl_seconds,
        )

    def relate_by_entity_ids(
        self,
        user_id: str,
        from_id: str,
        to_id: str,
        relation: str,
        *,
        source: str = "",
        weight: float = 1.0,
        ttl_seconds: Optional[int] = None,
    ) -> Optional[WorldRelation]:
        src = self.entity_by_id(user_id, from_id)
        dst = self.entity_by_id(user_id, to_id)
        if src is None or dst is None:
            return None
        rel = self.db.scalar(
            select(WorldRelation).where(
                WorldRelation.user_id == user_id,
                WorldRelation.from_id == src.id,
                WorldRelation.to_id == dst.id,
                WorldRelation.relation == relation,
            )
        )
        now = utcnow()
        if rel is None:
            rel = WorldRelation(
                id=token_id(),
                user_id=user_id,
                from_id=src.id,
                to_id=dst.id,
                relation=relation,
                source=source,
                weight=weight,
                first_seen=now,
                last_seen=now,
                ttl_seconds=ttl_seconds,
            )
            self.db.add(rel)
            self.db.flush()
        else:
            rel.last_seen = now
            rel.weight = max(rel.weight, weight)
            if ttl_seconds is not None:
                rel.ttl_seconds = ttl_seconds
        src.last_seen = now
        dst.last_seen = now
        return rel

    def remove_relation(
        self,
        user_id: str,
        from_type: str,
        from_key: str,
        relation: str,
        to_type: str,
        to_key: str,
    ) -> bool:
        src = self._resolve(user_id, from_type, from_key)
        dst = self._resolve(user_id, to_type, to_key)
        if src is None or dst is None:
            return False
        rel = self.db.scalar(
            select(WorldRelation).where(
                WorldRelation.user_id == user_id,
                WorldRelation.from_id == src.id,
                WorldRelation.to_id == dst.id,
                WorldRelation.relation == relation,
            )
        )
        if rel is None:
            return False
        self.db.delete(rel)
        return True

    # ---------------- queries ----------------

    def neighbors(
        self,
        user_id: str,
        entity_id: str,
        *,
        relation: Optional[str] = None,
        direction: str = "both",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        from_id = WorldRelation.from_id == entity_id
        to_id = WorldRelation.to_id == entity_id
        rel_clause = WorldRelation.relation == relation if relation else None
        q = select(WorldRelation).where(WorldRelation.user_id == user_id)
        if direction == "out":
            q = q.where(from_id)
        elif direction == "in":
            q = q.where(to_id)
        else:
            q = q.where(or_(from_id, to_id))
        if rel_clause is not None:
            q = q.where(rel_clause)
        rows = self.db.scalars(q.limit(limit)).all()
        results = []
        for r in rows:
            is_out = r.from_id == entity_id
            other_id = r.to_id if is_out else r.from_id
            other = self.entity_by_id(user_id, other_id)
            if other is None:
                continue
            results.append({
                "relation": r.relation,
                "direction": "out" if is_out else "in",
                "id": r.id,
                "entity": self._node(other),
            })
        return results

    def snapshot(
        self,
        user_id: str,
        *,
        center_type: Optional[str] = None,
        center_key: Optional[str] = None,
        depth: int = 2,
        limit: int = 400,
    ) -> Dict[str, Any]:
        """Return a subgraph: the center entity (or recent entities) + neighbors to `depth`."""
        node_map: Dict[str, WorldEntity] = {}
        edges: List[Dict[str, Any]] = []
        center_id = None

        if center_type and center_key:
            center = self._resolve(user_id, center_type, center_key)
            if center is None:
                return {"center": None, "nodes": [], "edges": []}
            center_id = center.id
            frontier: Dict[str, WorldEntity] = {center.id: center}
        else:
            recent = self.entities(user_id, limit=limit)
            frontier = {e.id: e for e in recent}
            depth = max(depth, 1)

        node_map.update(frontier)
        for _ in range(depth):
            if not frontier:
                break
            next_frontier: Dict[str, WorldEntity] = {}
            for eid in frontier:
                for n in self.neighbors(user_id, eid, limit=limit):
                    other = self.entity_by_id(user_id, n["entity"]["id"])
                    if other is None:
                        continue
                    node_map[other.id] = other
                    edges.append({"id": n["id"], "from": eid, "to": other.id, "relation": n["relation"]})
                    next_frontier[other.id] = other
            frontier = {k: v for k, v in next_frontier.items() if k not in node_map}

        seen_edges = {}
        for e in edges:
            seen_edges[(e["from"], e["to"], e["relation"])] = e["id"]
        return {
            "center": center_id,
            "nodes": [self._node(n) for n in node_map.values() if n is not None],
            "edges": [{"id": eid, "from": f, "to": t, "relation": r} for (f, t, r), eid in seen_edges.items()],
        }

    # ---------------- observations ----------------

    def journal(
        self,
        user_id: str,
        *,
        source: str,
        event_type: str,
        entity_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorldObservation:
        obs = WorldObservation(
            id=token_id(),
            user_id=user_id,
            source=source,
            event_type=event_type,
            entity_id=entity_id,
            payload_json=json.dumps(payload or {}, default=str),
        )
        self.db.add(obs)
        self.db.flush()
        return obs

    def observations(self, user_id: str, *, limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
        q = select(WorldObservation).where(WorldObservation.user_id == user_id)
        if source:
            q = q.where(WorldObservation.source == source)
        rows = self.db.scalars(q.order_by(WorldObservation.created_at.desc()).limit(limit)).all()
        return [self._observation(r) for r in rows]

    # ---------------- maintenance ----------------

    def purge_expired(self, user_id: str, *, now: Optional[datetime] = None) -> Dict[str, int]:
        """Delete entities/relations not observed within their TTL."""
        now = now or utcnow()
        cutoff = {}
        removed_entities = 0
        removed_relations = 0

        entities = self.db.scalars(
            select(WorldEntity).where(WorldEntity.user_id == user_id, WorldEntity.ttl_seconds.isnot(None))
        ).all()
        for e in entities:
            if e.last_seen + timedelta(seconds=e.ttl_seconds) < now:
                self.db.delete(e)
                removed_entities += 1

        relations = self.db.scalars(
            select(WorldRelation).where(WorldRelation.user_id == user_id, WorldRelation.ttl_seconds.isnot(None))
        ).all()
        for r in relations:
            if r.last_seen + timedelta(seconds=r.ttl_seconds) < now:
                self.db.delete(r)
                removed_relations += 1
        self.db.flush()
        return {"entities": removed_entities, "relations": removed_relations}

    # ---------------- serialization ----------------

    @staticmethod
    def _node(entity: WorldEntity) -> Dict[str, Any]:
        return {
            "id": entity.id,
            "type": entity.entity_type,
            "key": entity.key,
            "name": entity.name,
            "summary": entity.summary,
            "props": WorldGraph._props(entity),
            "source": entity.source,
            "confidence": entity.confidence,
            "first_seen": entity.first_seen.isoformat() if entity.first_seen else None,
            "last_seen": entity.last_seen.isoformat() if entity.last_seen else None,
        }

    @staticmethod
    def _props(entity: WorldEntity) -> Dict[str, Any]:
        try:
            return json.loads(entity.props_json or "{}")
        except Exception:
            return {}

    @staticmethod
    def _observation(obs: WorldObservation) -> Dict[str, Any]:
        return {
            "id": obs.id,
            "source": obs.source,
            "event_type": obs.event_type,
            "entity_id": obs.entity_id,
            "payload": json.loads(obs.payload_json or "{}"),
            "created_at": obs.created_at.isoformat() if obs.created_at else None,
        }


def token_id() -> str:
    from ...models import token_id as _token_id
    return _token_id()
