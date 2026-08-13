# backend/app/services/file_assistant.py
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import Document, KnowledgeChunk

log = logging.getLogger(__name__)


class FileAssistant:
    def __init__(self, db, gemini=None) -> None:
        self.db = db
        self._gemini = gemini

    def _context(self, user_id: str, *, max_chars: int = 8000) -> str:
        parts = []
        for d in self.db.scalars(select(Document).where(Document.user_id == user_id)).all():
            text = (d.extracted_text or "")[:2000]
            if text:
                parts.append(f"File: {d.filename}\n{text}")
        for c in self.db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.user_id == user_id)).all():
            parts.append(c.content[:1000])
        joined = "\n\n".join(parts)
        return joined[:max_chars]

    async def ask(self, user_id: str, question: str) -> Dict[str, Any]:
        context = self._context(user_id)
        if not context:
            return {"status": "ok", "answer": "No files or knowledge found to answer from.", "source_count": 0}
        if self._gemini is None:
            return {"status": "ok", "answer": context[:600], "source_count": 1, "note": "no model configured"}
        answer = await self._gemini.chat([
            {"role": "user", "content": f"Answer the user's question using ONLY the provided file context. If the context doesn't contain the answer, say so.\n\nQUESTION: {question}\n\nFILE CONTEXT:\n{context}"}
        ])
        return {"status": "ok", "answer": answer, "source_count": len(context.split("File: ")) - 1}
