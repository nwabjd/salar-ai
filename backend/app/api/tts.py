import logging
from typing import Optional

import edge_tts
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import ChatRequest
from ..security import get_current_user
from ..services.voice import VoiceService

router = APIRouter(tags=["tts"])
log = logging.getLogger(__name__)


@router.post("/api/tts")
async def text_to_speech(
    payload: ChatRequest,
    request: Request,
    fast: bool = Query(default=False),
    voice: Optional[str] = Query(default=None),
    rate: Optional[str] = Query(default=None),
    pitch: Optional[str] = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = payload.content.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    if not fast:
        gemini = getattr(request.app.state.coordinator, "gemini", None)
        if gemini:
            try:
                wav_bytes = await gemini.tts(text)
                return StreamingResponse(iter([wav_bytes]), media_type="audio/wav", headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                })
            except Exception as e:
                log.warning("Gemini TTS failed, falling back to edge-tts: %s", e)

    if voice:
        resolved_voice = voice
        resolved_rate = rate or ("+15%" if fast else "+5%")
        resolved_pitch = pitch or "+0Hz"
    else:
        params = VoiceService(db).tts_params(user.id)
        resolved_voice = params["voice"]
        resolved_rate = rate or params["rate"]
        resolved_pitch = pitch or params["pitch"]

    communicate = edge_tts.Communicate(text, resolved_voice, rate=resolved_rate, pitch=resolved_pitch)

    async def generate():
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    return StreamingResponse(generate(), media_type="audio/mpeg", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
