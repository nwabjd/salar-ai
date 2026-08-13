# backend/app/api/thought_stream.py
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.thought_stream import ThoughtStream

router = APIRouter(prefix="/api/thought-stream", tags=["thought-stream"])


def _serialize(item: dict) -> dict:
    data = dict(item)
    data["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
    return data


@router.get("")
def get_thought_stream(
    limit: int = 50,
    source: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = ThoughtStream(db).stream(user.id, limit=limit, source=source)
    return {"items": [_serialize(item) for item in items]}
