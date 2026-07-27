import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger(__name__)


class ReminderEngine:
    def __init__(self, engine=None, session_factory=None):
        self._task = None
        self._running = False
        self._engine = engine
        self._session_factory = session_factory

    def configure(self, engine, session_factory):
        self._engine = engine
        self._session_factory = session_factory

    async def start(self, interval: int = 30):
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(interval))
        log.info("Reminder engine started (interval=%ds)", interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self, interval: int):
        while self._running:
            try:
                await self._check_reminders()
            except Exception as e:
                log.error("Reminder check failed: %s", e)
            await asyncio.sleep(interval)

    async def _check_reminders(self):
        if not self._session_factory:
            return

        from ..models import Reminder

        now = datetime.now(timezone.utc)
        with self._session_factory() as db:
            due = db.execute(
                select(Reminder).where(
                    Reminder.is_done == False,
                    Reminder.notified == False,
                    Reminder.remind_at <= now
                )
            ).scalars().all()

            for r in due:
                r.notified = True
                log.info("Reminder due: '%s' for user %s", r.title, r.user_id)

                if r.recurrence and r.recurrence != "none":
                    if r.recurrence == "daily":
                        next_at = r.remind_at + timedelta(days=1)
                    elif r.recurrence == "weekly":
                        next_at = r.remind_at + timedelta(weeks=1)
                    elif r.recurrence == "monthly":
                        next_at = r.remind_at + timedelta(days=30)
                    else:
                        next_at = None

                    if next_at:
                        new_reminder = Reminder(
                            id=secrets.token_urlsafe(16)[:16],
                            user_id=r.user_id,
                            workspace_id=r.workspace_id,
                            title=r.title,
                            message=r.message,
                            remind_at=next_at,
                            recurrence=r.recurrence,
                            is_done=False,
                            notified=False,
                        )
                        db.add(new_reminder)

            if due:
                db.commit()


_engine = None


def get_engine() -> ReminderEngine:
    global _engine
    if _engine is None:
        _engine = ReminderEngine()
    return _engine
