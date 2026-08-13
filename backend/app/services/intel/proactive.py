# backend/app/services/intel/proactive.py
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ...models import ActionLog, IntelEvent, Reminder, Task
from .events import IntelEventStore

log = logging.getLogger(__name__)

DETECTORS = [
    "low_storage", "upcoming_appointments", "unfinished_work",
    "failed_builds", "unusual_cpu", "overdue_reminders",
]

_DEDUP_HOURS = 24


class ProactiveDetector:
    def __init__(self, db) -> None:
        self.db = db
        self._store = IntelEventStore(db)

    def _already_recorded(self, user_id: str, kind: str, title_key: str) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=_DEDUP_HOURS)
        rows = self.db.scalars(
            select(IntelEvent).where(
                IntelEvent.user_id == user_id,
                IntelEvent.kind == kind,
                IntelEvent.created_at >= cutoff,
            )
        ).all()
        return any(r.title.startswith(title_key) for r in rows)

    def _record(self, user_id: str, kind: str, severity: str, title: str, summary: str = "", detail=None, source="proactive") -> bool:
        if self._already_recorded(user_id, kind, title.split(":")[0]):
            return False
        self._store.record(user_id=user_id, kind=kind, severity=severity, title=title[:300], summary=summary, source=source, detail=detail)
        return True

    def scan(self, user_id: str, *, storage_free_pct: float = None, cpu_pct: float = None) -> int:
        """Run all detectors. Injected values used when provided (for tests). Returns # of new events."""
        count = 0
        count += self.scan_low_storage(user_id, free_pct=storage_free_pct)
        count += self.scan_upcoming(user_id)
        count += self.scan_unfinished(user_id)
        count += self.scan_failed_builds(user_id)
        count += self.scan_cpu(user_id, cpu_pct=cpu_pct)
        count += self.scan_overdue_reminders(user_id)
        return count

    def scan_low_storage(self, user_id: str, *, free_pct: float = None) -> int:
        if free_pct is None:
            try:
                import psutil
                free_pct = psutil.disk_usage("/").free / psutil.disk_usage("/").total * 100
            except Exception:
                return 0
        if free_pct is not None and free_pct < 10:
            ok = self._record(user_id, "low_storage", "warning", f"Low disk space: {free_pct:.0f}% free", summary="Free disk space dropped below 10%.")
            return 1 if ok else 0
        return 0

    def scan_upcoming(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=12)
        upcoming = self.db.scalars(
            select(Task).where(
                Task.user_id == user_id,
                Task.status != "done",
                Task.due_date >= now,
                Task.due_date <= soon,
            ).limit(5)
        ).all()
        count = 0
        for t in upcoming:
            if self._record(user_id, "upcoming_deadline", "info", f"Upcoming deadline: {t.title}", summary=f"Task due {t.due_date.isoformat()}"):
                count += 1
        return count

    def scan_unfinished(self, user_id: str) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=3)
        tasks = self.db.scalars(
            select(Task).where(
                Task.user_id == user_id,
                Task.status.in_(["todo", "in_progress"]),
                Task.created_at <= cutoff,
            ).limit(5)
        ).all()
        count = 0
        for t in tasks:
            if self._record(user_id, "unfinished_work", "info", f"Unfinished: {t.title}", summary="Task has been open for more than 3 days."):
                count += 1
        return count

    def scan_failed_builds(self, user_id: str) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        logs = self.db.scalars(
            select(ActionLog).where(
                ActionLog.user_id == user_id,
                ActionLog.created_at >= cutoff,
                ActionLog.tool.in_(["run_command", "code_run"]),
            ).limit(20)
        ).all()
        count = 0
        for a in logs:
            result = a.result_json or ""
            if result and ("error" in result.lower() or "failed" in result.lower()):
                if self._record(user_id, "failed_build", "warning", "Failed command detected", summary=f"Tool {a.tool} reported an error.", detail={"action_id": a.id}):
                    count += 1
        return count

    def scan_cpu(self, user_id: str, *, cpu_pct: float = None) -> int:
        if cpu_pct is None:
            try:
                import psutil
                cpu_pct = psutil.cpu_percent(interval=0.5)
            except Exception:
                return 0
        if cpu_pct is not None and cpu_pct > 85:
            ok = self._record(user_id, "high_cpu", "warning", f"High CPU usage: {cpu_pct:.0f}%", summary="CPU usage above 85%.")
            return 1 if ok else 0
        return 0

    def scan_overdue_reminders(self, user_id: str) -> int:
        now = datetime.now(timezone.utc)
        overdue = self.db.scalars(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_done.is_(False),
                Reminder.remind_at < now,
            ).limit(5)
        ).all()
        count = 0
        for r in overdue:
            if self._record(user_id, "overdue_reminder", "info", f"Overdue reminder: {r.title}", summary="Reminder passed without being completed."):
                count += 1
        return count
