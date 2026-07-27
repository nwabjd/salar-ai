from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Task
from ..security import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    workspace_id: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    tags: Optional[str] = ""


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    workspace_id: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None


@router.get("")
def list_tasks(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Task).filter(Task.user_id == current_user.id)

    if status:
        query = query.filter(Task.status == status)
    else:
        query = query.filter(Task.status != "archived")

    if priority:
        query = query.filter(Task.priority == priority)

    if workspace_id:
        query = query.filter(Task.workspace_id == workspace_id)

    tasks = query.order_by(Task.created_at.desc()).all()
    return [task_to_dict(t) for t in tasks]


@router.post("")
def create_task(
    req: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    due = None
    if req.due_date:
        try:
            due = datetime.fromisoformat(req.due_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    task = Task(
        user_id=current_user.id,
        title=req.title,
        description=req.description or "",
        workspace_id=req.workspace_id,
        priority=req.priority,
        due_date=due,
        tags=req.tags or "",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_to_dict(task)


@router.put("/{task_id}")
def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if req.title is not None:
        task.title = req.title
    if req.description is not None:
        task.description = req.description
    if req.workspace_id is not None:
        task.workspace_id = req.workspace_id
    if req.status is not None:
        task.status = req.status
    if req.priority is not None:
        task.priority = req.priority
    if req.due_date is not None:
        try:
            task.due_date = datetime.fromisoformat(req.due_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    if req.tags is not None:
        task.tags = req.tags

    now = datetime.now(timezone.utc)
    task.updated_at = now

    if req.status == "done":
        task.completed_at = now
    elif req.status is not None and req.status != "done" and task.completed_at is not None:
        task.completed_at = None

    db.commit()
    db.refresh(task)
    return task_to_dict(task)


@router.delete("/{task_id}")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}


@router.patch("/{task_id}/status")
def update_task_status(
    task_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.now(timezone.utc)
    task.status = status
    task.updated_at = now

    if status == "done":
        task.completed_at = now
    else:
        task.completed_at = None

    db.commit()
    db.refresh(task)
    return task_to_dict(task)


@router.get("/stats")
def task_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Task.status, func.count(Task.id))
        .filter(Task.user_id == current_user.id)
        .group_by(Task.status)
        .all()
    )
    stats = {"todo": 0, "in_progress": 0, "done": 0, "archived": 0}
    for status, count in rows:
        stats[status] = count
    stats["total"] = sum(stats.values())
    return stats


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "user_id": task.user_id,
        "workspace_id": task.workspace_id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "tags": task.tags,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }
