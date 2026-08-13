"""Clipboard intelligence endpoints — inspect clipboard and classify text."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clipboard", tags=["clipboard"])


class ClipboardAnalyzeRequest(BaseModel):
    text: str


@router.get("")
def inspect_clipboard(user: User = Depends(get_current_user)):
    from ..services.clipboard_intel import ClipboardIntelligence

    return ClipboardIntelligence().inspect()


@router.post("/analyze")
def analyze_clipboard(req: ClipboardAnalyzeRequest, user: User = Depends(get_current_user)):
    from ..services.clipboard_intel import ClipboardIntelligence

    return ClipboardIntelligence().classify(req.text)
