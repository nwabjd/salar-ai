"""
Semantic retrieval engine.

Uses ChromaDB for vector storage when available, with SQLite keyword
fallback.  Embeddings are generated via the NIM provider if a key is
configured; otherwise a deterministic local hash embedding is used so
the system never hard-fails.
"""
from __future__ import annotations

import hashlib
import logging
import struct
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Document, KnowledgeChunk, KnowledgeDocument, Memory

log = logging.getLogger(__name__)

_DIM = 256


def _hash_embed(text: str) -> List[float]:
    vec = [0.0] * _DIM
    words = text.lower().split()
    for w in words:
        digest = hashlib.sha256(w.encode()).digest()
        idx = struct.unpack_from("H", digest)[0] % _DIM
        vec[idx] += 1.0
    length = sum(v * v for v in vec) ** 0.5
    if length > 0:
        vec = [v / length for v in vec]
    return vec


_chroma_client = None
_chroma_available: Optional[bool] = None


def _get_chroma(path: str = "") -> Optional[Any]:
    global _chroma_client, _chroma_available
    if _chroma_available is False:
        return None
    try:
        import chromadb
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(path=path or None)
        _chroma_available = True
        return _chroma_client
    except Exception:
        _chroma_available = False
        return None


def _user_collection(user_id: str, path: str = ""):
    client = _get_chroma(path=path)
    if client is None:
        return None
    safe_id = user_id.replace("/", "_").replace("-", "_")[:20]
    return client.get_or_create_collection(
        name=f"salar_{safe_id}",
        metadata={"hnsw:space": "cosine"},
    )


async def _embed_texts(texts: List[str], nim=None, embedding_model: str = "") -> List[List[float]]:
    if nim and embedding_model:
        try:
            return await nim.embed(embedding_model, texts)
        except Exception as e:
            log.warning("NIM embed failed, using local fallback: %s", e)
    return [_hash_embed(t) for t in texts]


class SemanticSearch:
    def __init__(self, db: Session, nim=None, embedding_model: str = "", storage_path: str = "") -> None:
        self.db = db
        self._nim = nim
        self._embedding_model = embedding_model
        self._path = storage_path

    async def index_user(self, user_id: str) -> int:
        col = _user_collection(user_id, path=self._path)
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[dict] = []

        for doc in self.db.scalars(select(Document).where(Document.user_id == user_id)).all():
            text = (doc.extracted_text or "")[:4000]
            if text:
                ids.append(f"doc_{doc.id}")
                documents.append(text)
                metadatas.append({"source": "document", "title": doc.filename, "source_id": doc.id})

        for chunk in self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id)).all():
            text = chunk.content[:4000]
            if text:
                ids.append(f"kc_{chunk.id}")
                documents.append(text)
                metadatas.append({"source": "knowledge", "source_id": chunk.document_id, "chunk_index": chunk.chunk_index})

        for mem in self.db.scalars(select(Memory).where(Memory.user_id == user_id)).all():
            text = f"{mem.title} {mem.content}"[:4000]
            if text:
                ids.append(f"mem_{mem.id}")
                documents.append(text)
                metadatas.append({"source": "memory", "title": mem.title, "layer": mem.layer})

        if not ids or col is None:
            return 0

        embeddings = await _embed_texts(documents, self._nim, self._embedding_model)
        col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        return len(ids)

    async def query(self, user_id: str, query: str, *, limit: int = 10, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        col = _user_collection(user_id, path=self._path)
        if col is None or col.count() == 0:
            return self._keyword_fallback(user_id, q, limit=limit)

        q_emb = await _embed_texts([q], self._nim, self._embedding_model)

        where = None
        if source_filter:
            where = {"source": source_filter}

        try:
            result = col.query(
                query_embeddings=q_emb,
                n_results=min(limit, col.count() or 1),
                include=["documents", "metadatas", "distances"],
                where=where if where else None,
            )
        except Exception as e:
            log.warning("ChromaDB query failed, falling back to keyword: %s", e)
            return self._keyword_fallback(user_id, query, limit=limit)

        results: List[Dict[str, Any]] = []
        ids = result.get("ids", [[]])[0] if result.get("ids") else []
        distances = result.get("distances", [[]])[0] if result.get("distances") else []
        metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
        docs = result.get("documents", [[]])[0] if result.get("documents") else []

        for i, cid in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = distances[i] if i < len(distances) else 1.0
            score = 1.0 - dist
            snippet = (docs[i] if i < len(docs) else "")[:300]
            results.append({
                "id": cid,
                "source": meta.get("source", "unknown"),
                "title": meta.get("title", ""),
                "source_id": meta.get("source_id", ""),
                "snippet": snippet,
                "score": round(score, 4),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def _keyword_fallback(self, user_id: str, query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
        words = [w for w in query.split() if len(w) > 2]
        if not words:
            return []
        results: List[Dict[str, Any]] = []

        for doc in self.db.scalars(
            select(Document).where(
                Document.user_id == user_id,
                or_(*[Document.extracted_text.ilike(f"%{w}%") for w in words]),
            ).limit(limit)
        ).all():
            results.append({
                "id": f"doc_{doc.id}",
                "source": "document",
                "title": doc.filename,
                "source_id": doc.id,
                "snippet": (doc.extracted_text or "")[:300],
                "score": sum(1 for w in words if w.lower() in (doc.extracted_text or "").lower()) / len(words),
            })

        for chunk in self.db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.user_id == user_id,
                or_(*[KnowledgeChunk.content.ilike(f"%{w}%") for w in words]),
            ).limit(limit)
        ).all():
            results.append({
                "id": f"kc_{chunk.id}",
                "source": "knowledge",
                "title": "",
                "source_id": chunk.document_id,
                "snippet": chunk.content[:300],
                "score": sum(1 for w in words if w.lower() in chunk.content.lower()) / len(words),
            })

        for mem in self.db.scalars(
            select(Memory).where(
                Memory.user_id == user_id,
                or_(*[Memory.content.ilike(f"%{w}%") for w in words]),
            ).limit(limit)
        ).all():
            results.append({
                "id": f"mem_{mem.id}",
                "source": "memory",
                "title": mem.title,
                "source_id": mem.id,
                "snippet": mem.content[:300],
                "score": sum(1 for w in words if w.lower() in mem.content.lower()) / len(words),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
