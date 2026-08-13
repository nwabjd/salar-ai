# backend/app/api/guardian.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.guardian import GuardianAnalyzer
from ..services.intel.events import IntelEventStore

router = APIRouter(prefix="/api/guardian", tags=["guardian"])

_RULES = [
    "destructive command", "download-and-execute", "power/device control",
    "sensitive file overwrite", "outbound email", "process termination",
    "credential file access", "screen capture",
]


def _serialize(e) -> dict:
    import json
    return {
        "id": e.id,
        "severity": e.severity,
        "title": e.title,
        "summary": e.summary,
        "source": e.source,
        "detail": json.loads(e.detail_json or "{}"),
        "is_read": e.is_read,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/activity")
def guardian_activity(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    events = IntelEventStore(db).recent(current_user.id, kinds=["guardian"], limit=limit)
    return [_serialize(e) for e in events]


@router.get("/policy")
def guardian_policy():
    return {"rules": _RULES}
