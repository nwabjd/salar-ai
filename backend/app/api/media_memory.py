# backend/app/api/media_memory.py
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.media_memory import MEDIA_KINDS, MediaMemoryStore

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/media-memory", tags=["media-memory"])


class MediaMemoryRecord(BaseModel):
    kind: str
    caption: str = ""
    transcript: str = ""
    storage_path: str = ""


@router.post("")
def record_memory(payload: MediaMemoryRecord, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.kind not in MEDIA_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid media kind: {payload.kind}")
    ms = MediaMemoryStore(db)
    row = ms.record(user.id, payload.kind, caption=payload.caption, transcript=payload.transcript, storage_path=payload.storage_path)
    db.commit()
    return {"status": "ok", "id": row.id, "kind": row.kind}


@router.get("")
def list_memories(kind: Optional[str] = Query(None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind is not None and kind not in MEDIA_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid media kind: {kind}")
    return {"memories": MediaMemoryStore(db).list(user.id, kind=kind)}


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not MediaMemoryStore(db).delete(user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
    db.commit()
    return {"status": "ok"}
