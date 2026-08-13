# backend/app/services/widgets.py
import json
import logging
from typing import Any, Dict, List

from sqlalchemy import select

from ..models import WidgetPrefs, token_id, utcnow

log = logging.getLogger(__name__)

WIDGET_DEFINITIONS = [
    {"key": "missions", "name": "Missions", "size": "large", "refresh": 60},
    {"key": "tasks", "name": "Tasks", "size": "medium", "refresh": 300},
    {"key": "calendar", "name": "Calendar", "size": "medium", "refresh": 300},
    {"key": "email", "name": "Email Summary", "size": "small", "refresh": 300},
    {"key": "system", "name": "System Status", "size": "small", "refresh": 60},
    {"key": "intel", "name": "Intel Feed", "size": "large", "refresh": 60},
]


class WidgetService:
    def __init__(self, db) -> None:
        self.db = db

    def definitions(self) -> List[Dict[str, Any]]:
        return WIDGET_DEFINITIONS

    def save(self, user_id: str, widgets: List[str]) -> WidgetPrefs:
        row = self.db.scalar(select(WidgetPrefs).where(WidgetPrefs.user_id == user_id))
        if row is None:
            row = WidgetPrefs(id=token_id(), user_id=user_id, widgets_json=json.dumps(widgets), created_at=utcnow(), updated_at=utcnow())
            self.db.add(row)
            self.db.flush()
        else:
            row.widgets_json = json.dumps(widgets)
        return row

    def get(self, user_id: str) -> List[str]:
        row = self.db.scalar(select(WidgetPrefs).where(WidgetPrefs.user_id == user_id))
        if row is None:
            return [w["key"] for w in WIDGET_DEFINITIONS[:4]]
        try:
            return json.loads(row.widgets_json or "[]")
        except Exception:
            return []
