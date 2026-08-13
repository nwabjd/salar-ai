# backend/app/services/intel/predictive.py
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import select

from ...models import ActionLog

log = logging.getLogger(__name__)


class PredictiveEngine:
    def __init__(self, db) -> None:
        self.db = db

    def patterns(self, user_id: str, *, min_days: int = 2, min_occurrences: int = 2, window_hours: int = 2) -> List[Dict[str, Any]]:
        """Find repeated tool-usage patterns. Groups ActionLog rows by tool+hour bucket."""
        rows = self.db.scalars(
            select(ActionLog).where(ActionLog.user_id == user_id).order_by(ActionLog.created_at)
        ).all()
        by_tool: Dict[str, List[datetime]] = defaultdict(list)
        for r in rows:
            if r.created_at:
                by_tool[r.tool].append(r.created_at)

        patterns: List[Dict[str, Any]] = []
        for tool, times in by_tool.items():
            if len(times) < min_occurrences:
                continue
            hour_counts = Counter(t.hour for t in times)
            day_count = len({t.date() for t in times})
            if day_count < min_days:
                continue
            for hour, count in hour_counts.items():
                if count < min_occurrences:
                    continue
                patterns.append({
                    "tool": tool,
                    "hour": hour,
                    "occurrences": count,
                    "days": day_count,
                    "suggestion": self._suggestion(tool),
                })
        patterns.sort(key=lambda p: (-p["occurrences"], -p["days"]))
        return patterns

    def suggest_now(self, user_id: str, *, now: datetime = None) -> List[Dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        return [p for p in self.patterns(user_id) if p["hour"] == now.hour]

    @staticmethod
    def _suggestion(tool: str) -> str:
        friendly = {
            "open_app": "You normally open an app around this time. Open it?",
            "run_command": "You normally run a command around this time. Run it again?",
            "code_run": "You normally run code around this time. Run your usual script?",
            "browse_page": "You normally browse a page around this time. Revisit it?",
            "email_read": "You normally check email around this time. Check your inbox?",
            "file_write": "You normally save files around this time.",
        }
        return friendly.get(tool, f"You often use {tool} around this time. Use it now?")
