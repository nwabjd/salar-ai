"""UI analyzer endpoints — review UI screenshots for the Visual UI Builder."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..models import User
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ui-analyzer"])


@router.post("/ui-analyze")
async def ui_analyze(request: Request, file: UploadFile = File(...), user: User = Depends(get_current_user)):
    from ..services.ui_analyzer import UIAnalyzer

    gemini = getattr(getattr(request.app.state, "coordinator", None), "gemini", None)
    if gemini is None:
        raise HTTPException(status_code=503, detail="SALAR coordinator not available")
    data = await file.read()
    return await UIAnalyzer(gemini).analyze(data)
