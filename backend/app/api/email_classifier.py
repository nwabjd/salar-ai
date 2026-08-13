# backend/app/api/email_classifier.py
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.intel.email_classifier import classify_with_rules

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email-classifier"])


class EmailClassifyRequest(BaseModel):
    subject: str
    from_addr: str = ""
    body: str = ""


@router.post("/classify")
def classify_email(
    payload: EmailClassifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return classify_with_rules(payload.subject, payload.from_addr, payload.body)
