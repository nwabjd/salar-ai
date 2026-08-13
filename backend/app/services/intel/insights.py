# backend/app/services/intel/insights.py
import json
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select

from ...models import ActionLog, IntelEvent, Task

log = logging.getLogger(__name__)


class InsightEngine:
    def __init__(self, db) -> None:
        self.db = db

    def insights(self, user_id: str) -> List[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        insights: List[Dict[str, Any]] = []

        tools = self.db.scalars(select(ActionLog.tool).where(ActionLog.user_id == user_id, ActionLog.created_at >= week_ago)).all()
        tool_counter = Counter(tools)
        if tool_counter:
            top_tool, count = tool_counter.most_common(1)[0]
            insights.append({"kind": "usage_pattern", "title": f"Most-used tool this week: {top_tool}", "detail": f"Used {count} times in the last 7 days.", "severity": "info"})

        overdue = self.db.scalars(select(Task).where(Task.user_id == user_id, Task.status.in_(["todo", "in_progress"]), Task.due_date < now)).all()
        if overdue:
            insights.append({"kind": "overdue_tasks", "title": f"{len(overdue)} overdue task(s)", "detail": "Consider clearing or rescheduling.", "severity": "warning"})

        intel = self.db.scalars(select(IntelEvent).where(IntelEvent.user_id == user_id, IntelEvent.created_at >= week_ago)).all()
        if intel:
            insights.append({"kind": "intel_activity", "title": f"{len(intel)} background notices this week", "detail": "Review your intel stream for what SALAR noticed.", "severity": "info"})

        return insights
