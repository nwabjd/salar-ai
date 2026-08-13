# backend/app/api/presentation.py
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user
from ..services.presentation import PresentationBuilder

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presentation", tags=["presentation"])


class Slide(BaseModel):
    title: str = ""
    body: List[Any] = []


class BuildRequest(BaseModel):
    title: str
    slides: List[Slide] = []


@router.post("/build")
def build(request: BuildRequest, user: User = Depends(get_current_user)):
    slides = [{"title": s.title, "body": s.body} for s in request.slides]
    return {"html": PresentationBuilder().build_html(request.title, slides)}


@router.get("/outline")
def outline(topics: str = Query(""), user: User = Depends(get_current_user)):
    topics_list = [t.strip() for t in topics.split(",") if t.strip()]
    return {"slides": PresentationBuilder().outline(topics_list)}
