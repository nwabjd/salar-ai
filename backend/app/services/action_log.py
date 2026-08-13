# backend/app/services/action_log.py
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..models import ActionLog, token_id, utcnow

log = logging.getLogger(__name__)


class ActionLogger:
    def __init__(self, db) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: str,
        source: str,
        tool: str,
        args: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        is_undoable: bool = False,
        before_state: Optional[Dict[str, Any]] = None,
        undo_action: Optional[Dict[str, Any]] = None,
    ) -> ActionLog:
        action = ActionLog(
            id=token_id(),
            user_id=user_id,
            source=source,
            tool=tool,
            args_json=json.dumps(args or {}),
            result_json=json.dumps(result or {}),
            before_state_json=json.dumps(before_state or {}),
            undo_action_json=json.dumps(undo_action) if undo_action else "",
            is_undoable=is_undoable,
            undo_status="undoable" if is_undoable else "none",
            created_at=utcnow(),
        )
        self.db.add(action)
        self.db.flush()
        return action

    def list_for_user(self, db, user_id: str, *, limit: int = 100, tool: Optional[str] = None) -> List[ActionLog]:
        stmt = select(ActionLog).where(ActionLog.user_id == user_id)
        if tool:
            stmt = stmt.where(ActionLog.tool == tool)
        stmt = stmt.order_by(ActionLog.created_at.desc()).limit(limit)
        return list(db.scalars(stmt).all())

    def undo(self, db, action_id: str, user_id: str) -> bool:
        action = db.get(ActionLog, action_id)
        if action is None or action.user_id != user_id:
            return False
        if not action.is_undoable or not action.undo_action_json:
            return False
        if action.undo_status == "undone":
            return False
        try:
            undo = json.loads(action.undo_action_json)
            tool = undo.get("tool", "")
            args = undo.get("args", {})
            if tool in ("file_write", "write_file"):
                path = args.get("path")
                if not path:
                    raise ValueError("undo file_write missing path")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(args.get("content", ""))
            else:
                raise ValueError(f"no undo executor for tool {tool}")
            action.undo_status = "undone"
            db.add(action)
            return True
        except Exception as exc:
            log.exception("Undo failed for action %s: %s", action_id, exc)
            action.undo_status = "undo_failed"
            db.add(action)
            return False
