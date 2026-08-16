# backend/app/services/calendar_sync.py
"""Bridge between the in-memory calendar manager and the world graph.

The calendar manager lives in the API layer (`app.api.calendar`) as an
in-memory per-user map, so a clean way for background jobs to read it is
through this module. It returns raw event dicts for ingestion, or ``None``
when no feeds are configured.
"""

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def calendar_snapshot(user_id: str, *, days_before: int = 7, days_after: int = 30) -> Optional[List[Dict[str, Any]]]:
    """Best-effort snapshot of the user's calendar events, if feeds exist."""
    try:
        from ..api.calendar import _calendar_managers

        mgr = _calendar_managers.get(user_id)
        if mgr is None:
            return None
        return mgr.get_all_events(days_before=days_before, days_after=days_after)
    except Exception:
        log.exception("calendar_snapshot failed for %s", user_id)
        return None


def today_events(user_id: str) -> List[Dict[str, Any]]:
    """Events happening today, or [] when no calendar configured."""
    try:
        from ..api.calendar import _calendar_managers

        mgr = _calendar_managers.get(user_id)
        if mgr is None:
            return []
        return mgr.get_today_events()
    except Exception:
        log.exception("today_events failed for %s", user_id)
        return []
