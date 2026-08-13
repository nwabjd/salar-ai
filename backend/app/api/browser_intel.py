"""Browser intelligence endpoints — fetch and summarize web pages."""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browser", tags=["browser"])


def _gemini(request: Request):
    return getattr(getattr(request.app.state, "coordinator", None), "gemini", None)


class BrowserRequest(BaseModel):
    url: str


@router.post("/summarize")
async def summarize(req: BrowserRequest, request: Request, user: User = Depends(get_current_user)):
    from ..services.browser_intel import BrowserIntelligence

    return await BrowserIntelligence(_gemini(request)).summarize(req.url)


@router.post("/fetch")
async def fetch(req: BrowserRequest, request: Request, user: User = Depends(get_current_user)):
    from ..services.browser_intel import BrowserIntelligence

    return await BrowserIntelligence(_gemini(request)).fetch(req.url)
