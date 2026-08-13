"""Scheduler that enqueues recurring intelligence jobs.

Periodically enqueues `intel.email_watch` for every user with a configured email
account, and `brief.morning` for every user once per day. The actual work runs in
the worker; this scheduler only produces durable job rows, so missed ticks are
self-healing and crashes between ticks lose nothing already enqueued.
"""

import asyncio
import logging
from datetime import datetime, time, timezone
from typing import Optional, Set

from sqlalchemy import select

from ...models import User
from ..state import email_accounts
from .store import JobStore, utcnow

log = logging.getLogger(__name__)


class IntelScheduler:
    def __init__(
        self,
        *,
        session_factory,
        email_watch_interval_seconds: int = 900,
        morning_brief_hour: int = 7,
        morning_brief_minute: int = 0,
        timezone_name: str = "UTC",
    ) -> None:
        self.session_factory = session_factory
        self.email_watch_interval_seconds = email_watch_interval_seconds
        self.morning_brief_hour = morning_brief_hour
        self.morning_brief_minute = morning_brief_minute
        self._tz = timezone.utc if timezone_name == "UTC" else timezone.utc
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_email_watch: Optional[datetime] = None
        self._briefed_dates: Set[str] = set()

    # ---- lifecycle ----

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("IntelScheduler started (email watch every %ss, brief %02d:%02d)",
                 self.email_watch_interval_seconds, self.morning_brief_hour, self.morning_brief_minute)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # ---- loop ----

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("IntelScheduler tick error: %s", exc)
            await asyncio.sleep(15)

    async def _tick(self) -> None:
        now = utcnow()
        if self._last_email_watch is None or (now - self._last_email_watch).total_seconds() >= self.email_watch_interval_seconds:
            self._last_email_watch = now
            await self._schedule_email_watch()
        await self._schedule_morning_brief(now)

    # ---- scheduling ----

    async def _schedule_email_watch(self) -> None:
        user_ids = list(email_accounts.keys())
        if not user_ids:
            return
        with self.session_factory() as db:
            store = JobStore(db)
            enqueued = 0
            for user_id in user_ids:
                if not store.has_pending(user_id, "intel.email_watch"):
                    store.enqueue(user_id=user_id, kind="intel.email_watch", priority=1)
                    enqueued += 1
            if enqueued:
                db.commit()
                log.info("Enqueued %d email-watch job(s)", enqueued)

    async def _schedule_morning_brief(self, now: datetime) -> None:
        today = now.date().isoformat()
        local = now.astimezone(self._tz)
        # Compare wall-clock tuples to avoid naive/aware time mixing.
        if (local.hour, local.minute) < (self.morning_brief_hour, self.morning_brief_minute):
            return
        if today in self._briefed_dates:
            return
        with self.session_factory() as db:
            user_ids = list(db.scalars(select(User.id)).all())
            if not user_ids:
                return
            store = JobStore(db)
            for user_id in user_ids:
                if not store.has_pending(user_id, "brief.morning"):
                    store.enqueue(user_id=user_id, kind="brief.morning", priority=2)
            db.commit()
        self._briefed_dates.add(today)
        log.info("Enqueued morning brief for %d user(s)", len(user_ids))
