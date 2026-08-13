# backend/app/api/widgets.py
import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.widgets import WidgetService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


class WidgetsRequest(BaseModel):
    widgets: List[str]


@router.get("/definitions")
def widget_definitions(user: User = Depends(get_current_user)):
    return {"definitions": WidgetService(None).definitions()}


@router.get("")
def get_widgets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"widgets": WidgetService(db).get(user.id)}


@router.put("")
def save_widgets(payload: WidgetsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ws = WidgetService(db)
    ws.save(user.id, payload.widgets)
    db.commit()
    return {"status": "ok", "widgets": ws.get(user.id)}
