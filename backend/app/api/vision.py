"""Vision endpoints — analyze images, capture/analyze desktop screenshots, describe images."""

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

from ..models import User
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])


def _gemini(request: Request):
    gemini = getattr(getattr(request.app.state, "coordinator", None), "gemini", None)
    if gemini is None:
        raise HTTPException(status_code=503, detail="SALAR coordinator not available")
    return gemini


@router.post("/analyze")
async def analyze_image(
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form("What do you see in this image? Explain in detail."),
    user: User = Depends(get_current_user),
):
    from ..services.vision import VisionService

    data = await file.read()
    return await VisionService(_gemini(request)).analyze_image(data, prompt)


@router.post("/screenshot")
async def screenshot(request: Request, body: dict = None, user: User = Depends(get_current_user)):
    from ..services.vision import VisionService

    if body is None:
        body = {}
    prompt = body.get("prompt") or "What do you see in this screenshot? Explain in detail."
    try:
        return await VisionService(_gemini(request)).analyze_screenshot(prompt)
    except Exception as exc:
        log.error("Screenshot capture/analysis failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Screenshot unavailable: {exc}")


@router.get("/describe")
def describe(request: Request, user: User = Depends(get_current_user)):
    from ..services.vision import VisionService

    try:
        png = VisionService().capture_screenshot()
    except Exception as exc:
        log.error("Screenshot capture failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"Screenshot unavailable: {exc}")
    return VisionService().describe_image(png)
