"""Intel endpoints — background intelligence ledger, briefs, and background jobs."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.briefing import build_email_triage, build_intel_summary, build_morning_brief
from ..services.intel.events import IntelEventStore
from ..services.jobs.contracts import JobContext
from ..services.jobs.store import JobStore, utcnow

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intel", tags=["intel"])


@router.get("/events")
def list_events(
    request: Request,
    kinds: Optional[str] = None,
    unread_only: bool = False,
    severity: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = IntelEventStore(db)
    kind_list = [k.strip() for k in kinds.split(",") if k.strip()] if kinds else None
    events = store.recent(user.id, kinds=kind_list, unread_only=unread_only, severity=severity, limit=limit)
    return {"events": [IntelEventStore.to_dict(e) for e in events]}


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = IntelEventStore(db)
    return {"unread_count": store.unread_count(user.id)}


@router.post("/events/{event_id}/ack")
def ack_event(event_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = IntelEventStore(db)
    if not store.ack(event_id, user.id):
        raise HTTPException(status_code=404, detail="Event not found")
    db.commit()
    return {"status": "ok"}


@router.post("/ack-all")
def ack_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = IntelEventStore(db)
    count = store.ack_all(user.id)
    db.commit()
    return {"status": "ok", "acked": count}


@router.get("/brief")
def get_brief(
    brief_type: str = "morning",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if brief_type == "morning":
        return build_morning_brief(db, user.id)
    if brief_type == "email":
        return build_email_triage(db, user.id)
    if brief_type == "summary":
        return build_intel_summary(db, user.id)
    raise HTTPException(status_code=400, detail="brief_type must be morning, email, or summary")


@router.post("/watch/now")
def watch_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Enqueue an immediate email-watch job for this user."""
    from ..services.state import email_accounts

    if user.id not in email_accounts:
        raise HTTPException(status_code=400, detail="No email account configured")
    store = JobStore(db)
    if store.has_pending(user.id, "intel.email_watch"):
        return {"status": "already_pending"}
    job = store.enqueue(user_id=user.id, kind="intel.email_watch", priority=0)
    db.commit()
    return {"status": "enqueued", "job_id": job.id}


@router.get("/jobs")
def list_jobs(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = JobStore(db)
    jobs = store.list_for_user(user.id, limit=limit)
    return {"jobs": [_job_dict(j) for j in jobs]}


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    store = JobStore(db)
    job = store.get(job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    events = store.events(job_id)
    return {"events": [{"name": e.name, "status": e.status, "detail": _json(e.detail_json), "created_at": e.created_at.isoformat()} for e in events]}


def _job_dict(job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "priority": job.priority,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def _json(raw: str):
    import json

    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
