# backend/app/api/file_assistant.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.file_assistant import FileAssistant

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["file-assistant"])


class FileAskRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask(
    payload: FileAskRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")
    gemini = getattr(request.app.state, "coordinator", None)
    fa = FileAssistant(db, gemini=gemini.gemini if gemini is not None else None)
    return await fa.ask(user.id, question)
