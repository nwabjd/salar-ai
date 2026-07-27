import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..models import KnowledgeChunk, KnowledgeDocument, User
from ..security import get_current_user


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KnowledgeSearchRequest(BaseModel):
    query: str
    workspace_id: Optional[str] = None
    limit: int = 5


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += chunk_size - overlap
        if start + overlap >= len(words):
            break
    return chunks


@router.get("")
def list_documents(
    workspace_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.user_id == user.id)
    if workspace_id:
        stmt = stmt.where(KnowledgeDocument.workspace_id == workspace_id)
    stmt = stmt.order_by(KnowledgeDocument.created_at.desc())
    docs = list(db.scalars(stmt))
    return [
        {
            "id": d.id,
            "user_id": d.user_id,
            "workspace_id": d.workspace_id,
            "filename": d.filename,
            "content_type": d.content_type,
            "storage_path": d.storage_path,
            "full_text": d.full_text,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    workspace_id: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = Path(file.filename or "document.txt").name
    ext = Path(filename).suffix.lower()
    content = await file.read(request.app.state.settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > request.app.state.settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")

    text = ""
    if ext in (".txt", ".md"):
        text = content.decode("utf-8", errors="replace")
    else:
        text = content.decode("utf-8", errors="replace")

    doc_id = uuid.uuid4().hex[:32]
    storage_dir = request.app.state.settings.storage_dir / "knowledge" / user.id
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{doc_id}{ext}"
    file_path.write_bytes(content)

    doc = KnowledgeDocument(
        id=doc_id,
        user_id=user.id,
        workspace_id=workspace_id or None,
        filename=filename,
        content_type=file.content_type or "text/plain",
        storage_path=str(file_path),
        full_text=text,
        status="ready",
    )
    db.add(doc)
    db.flush()

    chunks = _chunk_text(text)
    for i, chunk_content in enumerate(chunks):
        chunk = KnowledgeChunk(
            document_id=doc_id,
            user_id=user.id,
            chunk_index=i,
            content=chunk_content,
            token_count=len(chunk_content.split()),
        )
        db.add(chunk)

    doc.chunk_count = len(chunks)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "user_id": doc.user_id,
        "workspace_id": doc.workspace_id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "storage_path": doc.storage_path,
        "full_text": doc.full_text,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.delete("/{doc_id}")
def delete_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user.id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    storage_path = Path(doc.storage_path)
    if storage_path.exists():
        storage_path.unlink(missing_ok=True)

    db.execute(KnowledgeChunk.__table__.delete().where(KnowledgeChunk.document_id == doc_id))
    db.delete(doc)
    db.commit()

    return {"ok": True, "deleted": doc_id}


@router.post("/search")
def search_knowledge(
    body: KnowledgeSearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        return []

    words = [w for w in re.split(r"\s+", query) if w]
    if not words:
        return []

    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeChunk.user_id == user.id)
    )
    if body.workspace_id:
        stmt = stmt.where(KnowledgeDocument.workspace_id == body.workspace_id)

    conditions = [KnowledgeChunk.content.ilike(f"%{w}%") for w in words]
    stmt = stmt.where(or_(*conditions))

    rows = list(db.execute(stmt))

    scored = []
    for chunk, doc in rows:
        lower_content = chunk.content.lower()
        score = sum(1 for w in words if w.lower() in lower_content)
        scored.append((score, chunk, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, chunk, doc in scored[: body.limit]:
        results.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "document_filename": doc.filename,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": score,
        })

    return results


@router.get("/{doc_id}/chunks")
def get_chunks(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id, KnowledgeDocument.user_id == user.id))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == doc_id)
            .order_by(KnowledgeChunk.chunk_index)
        )
    )
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "token_count": c.token_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chunks
    ]
