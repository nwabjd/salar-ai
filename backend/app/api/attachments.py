import io
import logging
from pathlib import Path

from docx import Document as DocxDocument
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Attachment, Conversation, Memory, User
from ..schemas import AttachmentCreate, AttachmentResponse
from ..security import get_current_user


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

ALLOWED = {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css", ".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _extract(ext: str, content: bytes) -> str:
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return ""
    if ext == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    if ext == ".docx":
        return "\n".join(p.text for p in DocxDocument(io.BytesIO(content)).paragraphs)
    return content.decode("utf-8", errors="replace")


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    conversation_id: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = Path(file.filename or "attachment").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    content = await file.read(request.app.state.settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > request.app.state.settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")

    conv = None
    if conversation_id:
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    record = Attachment(
        user_id=user.id,
        conversation_id=conversation_id or None,
        filename=filename,
        media_type=file.content_type or "application/octet-stream",
        storage_path="",
        size_bytes=len(content),
    )
    db.add(record)
    db.flush()

    target = request.app.state.settings.storage_dir / user.id / f"{record.id}{ext}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    record.storage_path = str(target)

    extracted = _extract(ext, content)
    try:
        coordinator = getattr(request.app.state, "coordinator", None)
        gemini = coordinator.gemini if coordinator is not None else None
        from ..services.artifact_analyzer import ArtifactAnalyzer

        analysis = await ArtifactAnalyzer(gemini).analyze(ext, content, text=extracted)
        analysis_text = analysis.get("description") or ""
        key_points = analysis.get("key_points") or []
        if key_points:
            analysis_text = analysis_text + "\n" + "\n".join(f"- {p}" for p in key_points)
        record.analysis = (analysis_text.strip() or extracted[:2000])[:50000]
    except Exception as exc:
        log.warning("Attachment analysis failed: %s", exc)
        record.analysis = (extracted or "")[:50000]

    if record.analysis and record.analysis.strip():
        try:
            mem = Memory(
                user_id=user.id,
                title=f"File: {filename}",
                content=record.analysis[:4000],
                kind="file",
                layer="short_term",
            )
            db.add(mem)
        except Exception as exc:
            log.warning("Artifact memory creation skipped: %s", exc)

    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[AttachmentResponse])
def list_attachments(
    conversation_id: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Attachment).where(Attachment.user_id == user.id)
    if conversation_id:
        query = query.where(Attachment.conversation_id == conversation_id)
    return list(db.scalars(query.order_by(Attachment.created_at.desc())))


@router.delete("/{attachment_id}")
def delete_attachment(attachment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.scalar(select(Attachment).where(Attachment.id == attachment_id, Attachment.user_id == user.id))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    if record.storage_path:
        try:
            Path(record.storage_path).unlink(missing_ok=True)
        except Exception:
            pass
    db.delete(record)
    db.commit()
    return {"status": "deleted", "id": attachment_id}