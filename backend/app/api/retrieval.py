"""
Semantic retrieval API — /api/retrieval
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.semantic_search import SemanticSearch

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


class SemanticQueryRequest(BaseModel):
    query: str
    limit: int = 10
    source_filter: Optional[str] = None


def _get_search(request: Request, db: Session) -> SemanticSearch:
    nim = getattr(request.app.state, "nim", None)
    model = getattr(request.app.state, "settings", None)
    model_name = getattr(model, "nim_default_model", "") if model else ""
    storage = getattr(getattr(request.app.state, "settings", None), "storage_dir", None)
    chroma_path = str(storage / "chroma") if storage else "/data/chroma"
    return SemanticSearch(db, nim=nim, embedding_model="nvidia/nv-embedqa-e5-v5" if nim else "", storage_path=chroma_path)


@router.post("/query")
async def semantic_query(
    body: SemanticQueryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    search = _get_search(request, db)
    results = await search.query(
        user.id,
        body.query,
        limit=min(max(body.limit, 1), 50),
        source_filter=body.source_filter,
    )
    return {"results": results, "count": len(results)}


@router.post("/index")
async def reindex(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
):
    search = _get_search(request, db)
    count = await search.index_user(user.id)
    return {"indexed": count, "status": "ok"}
