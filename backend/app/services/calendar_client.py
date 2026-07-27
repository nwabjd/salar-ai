"""Calendar service — fetch and parse iCal/CalDAV feeds."""

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from icalendar import Calendar
import recurring_ical_events
import httpx


class CalendarFeed:
    def __init__(self, name: str, url: str, color: str = "#5227FF"):
        self.name = name
        self.url = url
        self.color = color
        self._cache: dict = {"data": None, "time": 0}

    def _fetch(self, force=False) -> Calendar:
        now = time.time()
        if not force and self._cache["data"] and (now - self._cache["time"]) < 300:
            return self._cache["data"]

        headers = {"User-Agent": "SALAR/1.0 Calendar Reader"}
        # Google Calendar .ics URLs need accept header
        if "google.com" in self.url:
            headers["Accept"] = "text/calendar"

        resp = httpx.get(self.url, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        cal = Calendar.from_ical(resp.text)
        self._cache = {"data": cal, "time": now}
        return cal

    def get_events(self, days_before: int = 7, days_after: int = 30, force: bool = False) -> List[Dict[str, Any]]:
        cal = self._fetch(force=force)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days_before)
        end = now + timedelta(days=days_after)

        events = recurring_ical_events.of(cal).between(start, end)
        result = []
        for event in events:
            try:
                dtstart = event.get("dtstart")
                dtend = event.get("dtend")
                if not dtstart:
                    continue
                start_dt = dtstart.dt if hasattr(dtstart, "dt") else dtstart
                end_dt = dtend.dt if dtend and hasattr(dtend, "dt") else None

                # Make datetimes timezone-aware
                if isinstance(start_dt, datetime) and start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                if isinstance(end_dt, datetime) and end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)

                summary = str(event.get("summary", "Untitled"))
                description = str(event.get("description", "") or "")[:500]
                location = str(event.get("location", "") or "")
                uid = str(event.get("uid", ""))
                status = str(event.get("status", "") or "")
                all_day = isinstance(start_dt, datetime) and start_dt.hour == 0 and start_dt.minute == 0

                result.append({
                    "uid": uid,
                    "summary": summary,
                    "description": description,
                    "location": location,
                    "start": start_dt.isoformat() if isinstance(start_dt, datetime) else str(start_dt),
                    "end": end_dt.isoformat() if end_dt else None,
                    "all_day": all_day,
                    "status": status,
                    "calendar": self.name,
                    "color": self.color,
                })
            except Exception:
                continue

        result.sort(key=lambda e: e.get("start", ""))
        return result

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        events = self.get_events(days_before=90, days_after=90)
        q = query.lower()
        return [e for e in events if q in (e.get("summary", "").lower() or "") or q in (e.get("description", "").lower() or "")][:limit]


class CalendarManager:
    def __init__(self):
        self._feeds: Dict[str, CalendarFeed] = {}

    def add_feed(self, name: str, url: str, color: str = "#5227FF") -> Dict[str, Any]:
        feed = CalendarFeed(name, url, color)
        self._feeds[name] = feed
        try:
            events = feed.get_events(days_after=1)
            return {"status": "added", "name": name, "event_count": len(events)}
        except Exception as e:
            return {"status": "error", "name": name, "error": str(e)}

    def remove_feed(self, name: str) -> Dict[str, Any]:
        if name in self._feeds:
            del self._feeds[name]
            return {"status": "removed", "name": name}
        return {"error": f"Feed '{name}' not found"}

    def list_feeds(self) -> List[Dict[str, Any]]:
        return [{"name": f.name, "url": f.url, "color": f.color} for f in self._feeds.values()]

    def get_all_events(self, days_before: int = 7, days_after: int = 30) -> List[Dict[str, Any]]:
        all_events = []
        for feed in self._feeds.values():
            try:
                all_events.extend(feed.get_events(days_before=days_before, days_after=days_after))
            except Exception:
                continue
        all_events.sort(key=lambda e: e.get("start", ""))
        return all_events

    def get_today_events(self) -> List[Dict[str, Any]]:
        all_events = self.get_all_events(days_before=0, days_after=1)
        today = datetime.now(timezone.utc).date()
        result = []
        for e in all_events:
            try:
                start = e.get("start", "")
                if "T" in start:
                    dt = datetime.fromisoformat(start)
                    if dt.date() == today:
                        result.append(e)
                elif start.startswith(str(today)):
                    result.append(e)
            except Exception:
                continue
        return result

    def get_upcoming(self, limit: int = 10) -> List[Dict[str, Any]]:
        events = self.get_all_events(days_before=0, days_after=14)
        now = datetime.now(timezone.utc).isoformat()
        upcoming = [e for e in events if e.get("start", "") >= now]
        return upcoming[:limit]

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results = []
        for feed in self._feeds.values():
            try:
                results.extend(feed.search(query, limit))
            except Exception:
                continue
        results.sort(key=lambda e: e.get("start", ""))
        return results[:limit]
