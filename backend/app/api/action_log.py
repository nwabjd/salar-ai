# backend/app/api/action_log.py
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActionLog, User
from ..security import get_current_user
from ..services.action_log import ActionLogger

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _serialize(a: ActionLog) -> dict:
    return {
        "id": a.id,
        "source": a.source,
        "tool": a.tool,
        "args": json.loads(a.args_json or "{}"),
        "result": json.loads(a.result_json or "{}"),
        "is_undoable": a.is_undoable,
        "undo_status": a.undo_status,
        "undo_action": json.loads(a.undo_action_json) if a.undo_action_json else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("")
def list_actions(
    limit: int = 100,
    tool: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger = ActionLogger(db)
    rows = logger.list_for_user(db, current_user.id, limit=limit, tool=tool)
    return [_serialize(a) for a in rows]


@router.post("/{action_id}/undo")
def undo_action(
    action_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger = ActionLogger(db)
    ok = logger.undo(db, action_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=400, detail="Action not undoable or not found")
    db.commit()
    return {"status": "undone", "action_id": action_id}
