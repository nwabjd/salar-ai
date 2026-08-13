# backend/app/services/intel/doc_chunker.py
import logging
import re
from typing import Dict, List

log = logging.getLogger(__name__)


def chunk_sentences(text: str, *, target_chars: int = 500, overlap_chars: int = 60) -> List[str]:
    """Chunk text at sentence boundaries, targeting ~target_chars per chunk with overlap."""
    sentences = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    chunks: List[str] = []
    buf = ""
    for s in sentences:
        if len(buf) + len(s) + 1 > target_chars and buf:
            chunks.append(buf.strip())
            buf = buf[-overlap_chars:] + " " if overlap_chars else ""
        buf = (buf + " " + s).strip()
    if buf.strip():
        chunks.append(buf.strip())
    return chunks or ([text[:target_chars]] if text else [])


def chunk_with_metadata(text: str, *, title: str = "", source: str = "") -> List[Dict[str, str]]:
    """Sentence-aware chunks, each tagged with source title and chunk index metadata string."""
    chunks = chunk_sentences(text)
    return [
        {
            "content": c,
            "meta": {"title": title[:200], "source": source[:200], "chunk_index": i},
        }
        for i, c in enumerate(chunks)
    ]
