# backend/app/api/dynamic_memory.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.dynamic_memory import DynamicMemory

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["dynamic-memory"])


class MemoryMergeRequest(BaseModel):
    keep_id: str
    drop_id: str


@router.get("/duplicates")
def find_duplicates(
    threshold: float = 0.9,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dm = DynamicMemory(db)
    return {"pairs": dm.find_duplicates(user.id, threshold=threshold)}


@router.post("/merge")
def merge_memories(
    payload: MemoryMergeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dm = DynamicMemory(db)
    merged = dm.merge(user.id, payload.keep_id, payload.drop_id)
    if not merged:
        raise HTTPException(status_code=400, detail="Memories not found or not yours to merge")
    db.commit()
    return {"merged": True}


@router.post("/prune")
def prune_memories(
    max_age_days: int = 365,
    keep_recent: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dm = DynamicMemory(db)
    deleted = dm.prune_old(user.id, max_age_days=max_age_days, keep_recent=keep_recent)
    db.commit()
    return {"deleted": deleted}
