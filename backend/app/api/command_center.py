# backend/app/api/command_center.py
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Document, IntelEvent, Memory, Mission, Reminder, Task, User
from ..security import get_current_user
from ..services.intel.events import IntelEventStore
from ..services.thought_stream import ThoughtStream

router = APIRouter(prefix="/api", tags=["command-center"])

_ACTIVE_MISSION_STATUSES = ("queued", "planning", "running", "waiting_approval")
_CRITICAL_SEVERITIES = ("warning", "critical")


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _mission(m: Mission) -> dict:
    return {
        "id": m.id,
        "goal": m.goal,
        "status": m.status,
        "step_count": m.step_count,
        "completed_count": m.completed_count,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(m.updated_at),
    }


def _task(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "priority": t.priority,
        "due_date": _iso(t.due_date),
    }


def _stream_item(item: dict) -> dict:
    data = dict(item)
    data["created_at"] = item["created_at"].isoformat() if item["created_at"] else None
    return data


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    in_seven_days = now + timedelta(days=7)

    # ---- missions ----
    active_missions = db.scalars(
        select(Mission)
        .where(Mission.user_id == user.id, Mission.status.in_(_ACTIVE_MISSION_STATUSES))
        .order_by(Mission.created_at.desc())
        .limit(5)
    ).all()
    recent_completed = db.scalars(
        select(Mission)
        .where(Mission.user_id == user.id, Mission.status == "completed")
        .order_by(Mission.updated_at.desc())
        .limit(3)
    ).all()
    active_count = db.scalar(
        select(func.count(Mission.id)).where(
            Mission.user_id == user.id, Mission.status.in_(_ACTIVE_MISSION_STATUSES)
        )
    ) or 0
    completed_count = db.scalar(
        select(func.count(Mission.id)).where(
            Mission.user_id == user.id, Mission.status == "completed"
        )
    ) or 0

    # ---- tasks ----
    open_tasks = select(Task).where(Task.user_id == user.id, Task.status.not_in(("done", "archived")))
    overdue = db.scalars(
        open_tasks.where(Task.due_date.isnot(None), Task.due_date < now)
        .order_by(Task.due_date.asc())
        .limit(5)
    ).all()
    today = db.scalars(
        open_tasks.where(Task.due_date.isnot(None), Task.due_date >= today_start, Task.due_date < tomorrow_start)
        .order_by(Task.due_date.asc())
        .limit(5)
    ).all()
    upcoming = db.scalars(
        open_tasks.where(Task.due_date.isnot(None), Task.due_date >= tomorrow_start, Task.due_date <= in_seven_days)
        .order_by(Task.due_date.asc())
        .limit(5)
    ).all()
    total_pending = db.scalar(
        select(func.count(Task.id)).where(Task.user_id == user.id, Task.status.not_in(("done", "archived")))
    ) or 0

    # ---- calendar ----
    upcoming_reminders = db.scalars(
        select(Reminder)
        .where(Reminder.user_id == user.id, Reminder.is_done.is_(False), Reminder.remind_at > now)
        .order_by(Reminder.remind_at.asc())
        .limit(5)
    ).all()

    # ---- email (intel) ----
    store = IntelEventStore(db)
    unread_count = store.unread_count(user.id)
    critical_recent = db.scalars(
        select(IntelEvent)
        .where(IntelEvent.user_id == user.id, IntelEvent.severity.in_(_CRITICAL_SEVERITIES))
        .order_by(IntelEvent.created_at.desc(), IntelEvent.seq.desc())
        .limit(3)
    ).all()

    # ---- guardian ----
    recent_flags = store.recent(user.id, kinds=["guardian"], limit=5)
    flag_count = db.scalar(
        select(func.count(IntelEvent.id)).where(
            IntelEvent.user_id == user.id,
            IntelEvent.kind == "guardian",
            IntelEvent.is_read.is_(False),
        )
    ) or 0

    # ---- thought stream ----
    try:
        stream_items = ThoughtStream(db).stream(user.id, limit=10)
    except Exception:
        stream_items = []

    # ---- memory / files ----
    memory_total = db.scalar(select(func.count(Memory.id)).where(Memory.user_id == user.id)) or 0
    recent_memories = db.scalars(
        select(Memory).where(Memory.user_id == user.id).order_by(Memory.updated_at.desc()).limit(3)
    ).all()
    total_documents = db.scalar(select(func.count(Document.id)).where(Document.user_id == user.id)) or 0

    return {
        "missions": {
            "active": [_mission(m) for m in active_missions],
            "recent_completed": [_mission(m) for m in recent_completed],
            "active_count": active_count,
            "completed_count": completed_count,
        },
        "tasks": {
            "overdue": [_task(t) for t in overdue],
            "today": [_task(t) for t in today],
            "upcoming": [_task(t) for t in upcoming],
            "total_pending": total_pending,
        },
        "calendar": {
            "upcoming_reminders": [
                {"id": r.id, "title": r.title, "message": r.message, "remind_at": _iso(r.remind_at)}
                for r in upcoming_reminders
            ]
        },
        "email": {
            "unread_count": unread_count,
            "critical_recent": [
                {
                    "id": e.id,
                    "kind": e.kind,
                    "severity": e.severity,
                    "title": e.title,
                    "summary": e.summary,
                    "created_at": _iso(e.created_at),
                }
                for e in critical_recent
            ],
        },
        "guardian": {
            "recent_flags": [
                {"id": e.id, "severity": e.severity, "title": e.title, "created_at": _iso(e.created_at)}
                for e in recent_flags
            ],
            "flag_count": flag_count,
        },
        "thought_stream": {
            "items": [_stream_item(i) for i in stream_items],
            "count": len(stream_items),
        },
        "memory": {
            "total": memory_total,
            "recent": [
                {"id": m.id, "title": m.title, "kind": m.kind, "updated_at": _iso(m.updated_at)}
                for m in recent_memories
            ],
        },
        "files": {"total_documents": total_documents},
        "user": {"id": user.id, "name": user.email},
    }
