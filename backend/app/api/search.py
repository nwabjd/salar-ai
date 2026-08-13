# backend/app/api/search.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.universal_search import SEARCHABLE_SOURCES, UniversalSearch

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    q: str = "",
    limit: int = 20,
    sources: List[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Missing search query")
    per_source = max(1, limit // 10)
    results = UniversalSearch(db).search(user.id, q, sources=sources, limit_per_source=per_source)
    return {"query": q, "results": results}


@router.get("/sources")
def sources():
    return {"sources": SEARCHABLE_SOURCES}
