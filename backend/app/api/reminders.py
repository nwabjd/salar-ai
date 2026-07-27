from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional

from ..security import get_current_user
from ..database import get_db
from ..models import User, Reminder

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("")
def list_reminders(
    upcoming_only: bool = Query(False),
    limit: int = Query(50, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Reminder).filter(Reminder.user_id == user.id)
    if upcoming_only:
        q = q.filter(Reminder.remind_at > datetime.now(timezone.utc))
        q = q.filter(Reminder.is_done == False)
    q = q.order_by(Reminder.remind_at.desc())
    rows = q.limit(limit).all()
    return [r.__dict__ for r in rows]


@router.post("", status_code=201)
def create_reminder(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = body.get("title")
    if not title:
        raise HTTPException(400, "title is required")

    remind_at_raw = body.get("remind_at")
    if not remind_at_raw:
        raise HTTPException(400, "remind_at is required")

    if isinstance(remind_at_raw, str):
        remind_at = datetime.fromisoformat(remind_at_raw.replace("Z", "+00:00"))
    else:
        remind_at = remind_at_raw

    if isinstance(remind_at, datetime) and remind_at.tzinfo is None:
        remind_at = remind_at.replace(tzinfo=timezone.utc)

    recurrence = body.get("recurrence", "none")
    if recurrence not in ("none", "daily", "weekly", "monthly"):
        raise HTTPException(400, "recurrence must be none, daily, weekly, or monthly")

    r = Reminder(
        id=f"rem_{user.id}_{int(datetime.now(timezone.utc).timestamp())}",
        user_id=user.id,
        workspace_id=body.get("workspace_id"),
        title=title,
        message=body.get("message", ""),
        remind_at=remind_at,
        recurrence=recurrence,
        is_done=False,
        notified=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r.__dict__


@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Reminder).filter(
        Reminder.id == reminder_id, Reminder.user_id == user.id
    ).first()
    if not r:
        raise HTTPException(404, "Reminder not found")

    if "title" in body:
        r.title = body["title"]
    if "message" in body:
        r.message = body["message"]
    if "workspace_id" in body:
        r.workspace_id = body["workspace_id"]
    if "recurrence" in body:
        rec = body["recurrence"]
        if rec not in ("none", "daily", "weekly", "monthly"):
            raise HTTPException(400, "recurrence must be none, daily, weekly, or monthly")
        r.recurrence = rec
    if "remind_at" in body:
        raw = body["remind_at"]
        if isinstance(raw, str):
            r.remind_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            r.remind_at = raw
        if isinstance(r.remind_at, datetime) and r.remind_at.tzinfo is None:
            r.remind_at = r.remind_at.replace(tzinfo=timezone.utc)
    if "is_done" in body:
        r.is_done = bool(body["is_done"])
    if "notified" in body:
        r.notified = bool(body["notified"])

    db.commit()
    db.refresh(r)
    return r.__dict__


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Reminder).filter(
        Reminder.id == reminder_id, Reminder.user_id == user.id
    ).first()
    if not r:
        raise HTTPException(404, "Reminder not found")
    db.delete(r)
    db.commit()


@router.patch("/{reminder_id}/done")
def mark_done(
    reminder_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = db.query(Reminder).filter(
        Reminder.id == reminder_id, Reminder.user_id == user.id
    ).first()
    if not r:
        raise HTTPException(404, "Reminder not found")
    r.is_done = True
    db.commit()
    db.refresh(r)
    return r.__dict__


@router.get("/overdue")
def get_overdue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Reminder)
        .filter(
            Reminder.user_id == user.id,
            Reminder.is_done == False,
            Reminder.remind_at <= now,
        )
        .order_by(Reminder.remind_at.asc())
        .all()
    )
    return [r.__dict__ for r in rows]
