# backend/app/api/automation.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import IntelEvent, User
from ..security import get_current_user
from ..services.automation import AutomationManager
from ..services.notifications import NotificationCenter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automation"])


class ProcessIntelRequest(BaseModel):
    intel_event_id: str


@router.post("/process-intel")
def process_intel_event(
    payload: ProcessIntelRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.get(IntelEvent, payload.intel_event_id)
    if event is None or event.user_id != user.id:
        raise HTTPException(status_code=404, detail="Intel event not found")
    notification = AutomationManager(db).process_intel_event(user.id, event)
    db.commit()
    if notification is None:
        return {"notification": None}
    return {"notification": NotificationCenter(db)._serialize(notification)}
