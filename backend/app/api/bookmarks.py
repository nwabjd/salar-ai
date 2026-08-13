# backend/app/api/bookmarks.py
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.bookmarks import BookmarkManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


class BookmarkCreate(BaseModel):
    url: str
    title: str = ""
    summary: str = ""
    tags: List[str] = []


@router.get("")
def list_bookmarks(
    tag: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    manager = BookmarkManager(db)
    return {"bookmarks": manager.list(user.id, tag=tag, q=q, limit=limit)}


@router.post("")
def add_bookmark(
    payload: BookmarkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.url:
        raise HTTPException(status_code=400, detail="url is required")
    manager = BookmarkManager(db)
    bookmark = manager.add(user.id, payload.url, title=payload.title, summary=payload.summary, tags=payload.tags)
    db.commit()
    return {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "summary": bookmark.summary,
        "tags": manager._tags(bookmark),
    }


@router.delete("/{bookmark_id}")
def delete_bookmark(
    bookmark_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    manager = BookmarkManager(db)
    if not manager.delete(user.id, bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.commit()
    return {"status": "deleted"}
