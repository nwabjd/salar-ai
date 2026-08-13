# backend/app/services/intel/eod_memory.py
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, select

from ...models import ActionLog, IntelEvent, Memory, Mission, Reminder, Task
from .events import IntelEventStore

log = logging.getLogger(__name__)


class EndOfDayMemory:
    def __init__(self, db) -> None:
        self.db = db
        self._store = IntelEventStore(db)

    def build(self, user_id: str, *, day: Optional[datetime] = None) -> Dict[str, Any]:
        """Build the end-of-day summary for a user. `day` defaults to today (UTC)."""
        now = day or datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # completed today
        missions_completed = self.db.scalars(
            select(Mission).where(
                Mission.user_id == user_id,
                Mission.finished_at >= day_start,
                Mission.finished_at < day_end,
                Mission.status == "completed",
            )
        ).all()
        tasks_completed = self.db.scalars(
            select(Task).where(
                Task.user_id == user_id,
                Task.updated_at >= day_start,
                Task.updated_at < day_end,
                Task.status == "done",
            )
        ).all()
        actions_today = int(
            self.db.scalar(
                select(func.count(ActionLog.id)).where(
                    ActionLog.user_id == user_id,
                    ActionLog.created_at >= day_start,
                    ActionLog.created_at < day_end,
                )
            ) or 0
        )

        # unfinished
        open_tasks = self.db.scalars(
            select(Task).where(
                Task.user_id == user_id,
                Task.status.in_(["todo", "in_progress"]),
            ).limit(10)
        ).all()
        pending_reminders = self.db.scalars(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_done.is_(False),
            ).limit(10)
        ).all()

        # activity
        intel_today = self.db.scalars(
            select(IntelEvent).where(
                IntelEvent.user_id == user_id,
                IntelEvent.created_at >= day_start,
                IntelEvent.created_at < day_end,
            ).order_by(IntelEvent.seq.desc()).limit(10)
        ).all()

        summary = {
            "date": day_start.date().isoformat(),
            "completed": {
                "missions": [{"id": m.id, "goal": m.goal} for m in missions_completed],
                "tasks": [{"id": t.id, "title": t.title} for t in tasks_completed],
                "actions": actions_today,
            },
            "unfinished": {
                "tasks": [{"id": t.id, "title": t.title, "priority": t.priority, "due_date": t.due_date.isoformat() if t.due_date else None} for t in open_tasks],
                "reminders": [{"id": r.id, "title": r.title, "remind_at": r.remind_at.isoformat() if r.remind_at else None} for r in pending_reminders],
            },
            "activity": [
                {"kind": e.kind, "severity": e.severity, "title": e.title, "created_at": e.created_at.isoformat() if e.created_at else None}
                for e in intel_today
            ],
            "suggested_tomorrow": [t["title"] for t in ({"id": t.id, "title": t.title} for t in open_tasks)][:5],
        }
        return summary

    def record(self, user_id: str, *, day: Optional[datetime] = None) -> bool:
        """Persist the EOD summary as an intel event (kind='eod', source='eod'). Dedup: only one per day."""
        now = day or datetime.now(timezone.utc)
        existing = self.db.scalar(
            select(IntelEvent).where(
                IntelEvent.user_id == user_id,
                IntelEvent.kind == "eod",
                IntelEvent.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
            )
        )
        if existing:
            return False
        summary = self.build(user_id, day=now)
        self._store.record(
            user_id=user_id,
            kind="eod",
            severity="info",
            title=f"End of Day — {now.strftime('%B %d, %Y')}",
            summary=json.dumps(summary),
            source="eod",
            detail={"date": now.date().isoformat()},
        )
        self.db.commit()
        return True
