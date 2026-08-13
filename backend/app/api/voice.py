# backend/app/api/voice.py
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import get_current_user
from ..services.voice import PERSONALITIES, STYLE_PRESETS, VoiceService

router = APIRouter(tags=["voice"])
log = logging.getLogger(__name__)


class VoicePrefsUpdate(BaseModel):
    voice: Optional[str] = None
    style: Optional[str] = None
    personality: Optional[str] = None
    rate: Optional[str] = None
    pitch: Optional[str] = None
    wake_word_enabled: Optional[bool] = None
    wake_phrase: Optional[str] = None
    interruption_enabled: Optional[bool] = None


class WakeCheck(BaseModel):
    transcript: str


def _prefs_dict(prefs) -> dict:
    return {
        "voice": prefs.voice,
        "style": prefs.style,
        "personality": prefs.personality,
        "rate": prefs.rate,
        "pitch": prefs.pitch,
        "wake_word_enabled": prefs.wake_word_enabled,
        "wake_phrase": prefs.wake_phrase,
        "interruption_enabled": prefs.interruption_enabled,
    }


def _prefs_response(db: Session, user: User) -> dict:
    vs = VoiceService(db)
    prefs = vs.prefs_for(user.id)
    return {
        "preferences": _prefs_dict(prefs),
        "tts_params": vs.apply_style(prefs),
        "styles": list(STYLE_PRESETS),
        "personalities": list(PERSONALITIES),
    }


@router.get("/api/voice/preferences")
def get_voice_preferences(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _prefs_response(db, user)


@router.put("/api/voice/preferences")
def update_voice_preferences(
    payload: VoicePrefsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vs = VoiceService(db)
    prefs = vs.prefs_for(user.id)
    fields = (
        "voice", "style", "personality", "rate", "pitch",
        "wake_word_enabled", "wake_phrase", "interruption_enabled",
    )
    for field in fields:
        value = getattr(payload, field)
        if value is not None:
            setattr(prefs, field, value)
    db.commit()
    return {
        "preferences": _prefs_dict(prefs),
        "tts_params": vs.apply_style(prefs),
        "styles": list(STYLE_PRESETS),
        "personalities": list(PERSONALITIES),
    }


@router.post("/api/voice/wake")
def check_wake(
    payload: WakeCheck,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vs = VoiceService(db)
    prefs = vs.prefs_for(user.id)
    return {"matched": vs.wake_detect(payload.transcript, prefs.wake_phrase), "phrase": prefs.wake_phrase}


@router.get("/api/voice/styles")
def list_styles():
    return {"styles": list(STYLE_PRESETS), "personalities": list(PERSONALITIES)}
