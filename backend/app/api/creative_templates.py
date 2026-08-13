# backend/app/api/creative_templates.py
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user
from ..services.creative_templates import CreativeTemplates

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])


class RenderRequest(BaseModel):
    template_key: str
    variables: Dict[str, str] = {}


@router.get("")
def list_templates(user: User = Depends(get_current_user)):
    return {"templates": CreativeTemplates().list()}


@router.post("/render")
def render_template(payload: RenderRequest, user: User = Depends(get_current_user)):
    result = CreativeTemplates().render(payload.template_key, payload.variables)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("detail", "render failed"))
    return result
