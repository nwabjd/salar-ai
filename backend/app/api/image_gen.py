# backend/app/api/image_gen.py
import base64
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user
from ..services.image_gen import ImageGenerator

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/images", tags=["images"])


class GenerateRequest(BaseModel):
    prompt: str
    count: int = 1
    aspect_ratio: str = "1:1"


def _api_key(request: Request) -> Optional[str]:
    settings = getattr(request.app.state, "settings", None)
    if settings is not None:
        return getattr(settings, "gemini_api_key", None)
    return os.environ.get("GEMINI_API_KEY")


@router.post("/generate")
async def generate_image(request: Request, payload: GenerateRequest, user: User = Depends(get_current_user)):
    result = await ImageGenerator(_api_key(request)).generate(payload.prompt, count=payload.count, aspect_ratio=payload.aspect_ratio)
    if result.get("status") == "unavailable":
        raise HTTPException(status_code=503, detail=result.get("detail", "image generation unavailable"))
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("detail", "image generation failed"))
    return {
        "status": "ok",
        "count": result.get("count", 0),
        "images": [base64.b64encode(img).decode("ascii") for img in result.get("images", [])],
    }
