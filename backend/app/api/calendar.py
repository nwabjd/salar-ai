"""Calendar endpoints — iCal/CalDAV feed management and event queries."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from ..security import get_current_user
from ..models import User

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# In-memory calendar manager per-user
_calendar_managers: dict = {}


def _get_manager(user_id: str):
    from ..services.calendar_client import CalendarManager
    if user_id not in _calendar_managers:
        _calendar_managers[user_id] = CalendarManager()
    return _calendar_managers[user_id]


class FeedAddRequest(BaseModel):
    name: str
    url: str
    color: str = "#5227FF"


class EventSearchRequest(BaseModel):
    query: str
    limit: int = 20


@router.post("/feeds")
def add_feed(req: FeedAddRequest, user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    try:
        return mgr.add_feed(req.name, req.url, req.color)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/feeds/{name}")
def remove_feed(name: str, user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    return mgr.remove_feed(name)


@router.get("/feeds")
def list_feeds(user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    return {"feeds": mgr.list_feeds()}


@router.get("/events")
def get_events(days_before: int = 7, days_after: int = 30, user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    events = mgr.get_all_events(days_before=days_before, days_after=days_after)
    return {"events": events, "count": len(events)}


@router.get("/today")
def today_events(user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    events = mgr.get_today_events()
    return {"events": events, "count": len(events)}


@router.get("/upcoming")
def upcoming_events(limit: int = 10, user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    events = mgr.get_upcoming(limit)
    return {"events": events, "count": len(events)}


@router.post("/search")
def search_events(req: EventSearchRequest, user: User = Depends(get_current_user)):
    mgr = _get_manager(user.id)
    events = mgr.search(req.query, req.limit)
    return {"events": events, "count": len(events)}
