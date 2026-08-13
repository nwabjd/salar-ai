# backend/app/api/notifications.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.notifications import NotificationCenter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nc = NotificationCenter(db)
    return {"notifications": nc.list(user.id, unread_only=unread_only, limit=limit)}


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    nc = NotificationCenter(db)
    return {"unread_count": nc.unread_count(user.id)}


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    nc = NotificationCenter(db)
    if not nc.mark_read(user.id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"status": "ok"}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    nc = NotificationCenter(db)
    count = nc.mark_all_read(user.id)
    db.commit()
    return {"status": "ok", "marked_read": count}
