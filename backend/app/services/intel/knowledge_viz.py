# backend/app/services/intel/knowledge_viz.py
import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List

from sqlalchemy import select

from ...models import KnowledgeChunk, Memory

log = logging.getLogger(__name__)

STOPWORDS = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is", "are", "this", "that", "it", "at", "by", "from"}


class KnowledgeVisualization:
    def __init__(self, db) -> None:
        self.db = db

    def topic_clusters(self, user_id: str, *, max_topics: int = 8) -> Dict[str, Any]:
        """Cluster knowledge + memory by kind, with top keyword per cluster."""
        kinds: Dict[str, List[str]] = defaultdict(list)
        for m in self.db.scalars(select(Memory).where(Memory.user_id == user_id)).all():
            kinds[m.kind].append(f"{m.title} {m.content}")
        for c in self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id)).all():
            kinds["knowledge"].append(c.content)
        clusters = []
        for kind, texts in kinds.items():
            counter: Counter = Counter()
            for t in texts:
                for w in re.findall(r"[A-Za-z]{4,}", t.lower()):
                    if w not in STOPWORDS:
                        counter[w] += 1
            top = [w for w, _ in counter.most_common(6)]
            clusters.append({"kind": kind, "count": len(texts), "top_keywords": top})
        clusters.sort(key=lambda c: -c["count"])
        return {"clusters": clusters[:max_topics], "total": len(kinds)}
