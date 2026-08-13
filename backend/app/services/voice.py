# backend/app/services/voice.py
import logging
import re
from typing import Any, Dict, Optional

from ..models import VoicePreferences

log = logging.getLogger(__name__)

STYLE_PRESETS = {
    "neutral": {"voice": "en-US-AriaNeural", "rate": "+0%", "pitch": "+0Hz"},
    "cheerful": {"voice": "en-US-JennyNeural", "rate": "+8%", "pitch": "+2Hz"},
    "serious": {"voice": "en-US-GuyNeural", "rate": "-4%", "pitch": "-3Hz"},
    "whisper": {"voice": "en-US-AriaNeural", "rate": "-25%", "pitch": "+0Hz", "volume": "-40%"},
    "energetic": {"voice": "en-US-AnaNeural", "rate": "+15%", "pitch": "+4Hz"},
}

PERSONALITIES = {
    "default": "You are SALAR, a helpful AI assistant.",
    "professional": "You are SALAR, a polished, professional assistant. Be precise and formal.",
    "friendly": "You are SALAR, a warm, friendly companion. Be casual and encouraging.",
    "concise": "You are SALAR. Answer briefly and get straight to the point.",
}

WAKE_VARIANTS = {}


def normalize(phrase: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (phrase or "").lower()).strip()


class VoiceService:
    def __init__(self, db) -> None:
        self.db = db

    def prefs_for(self, user_id: str) -> VoicePreferences:
        row = self.db.query(VoicePreferences).filter(VoicePreferences.user_id == user_id).first()
        if row is None:
            row = VoicePreferences(id="vp_" + user_id, user_id=user_id)
            self.db.add(row)
            self.db.flush()
        return row

    def apply_style(self, prefs: VoicePreferences) -> Dict[str, Any]:
        style = prefs.style if prefs.style in STYLE_PRESETS else "neutral"
        preset = dict(STYLE_PRESETS[style])
        if not prefs.voice or prefs.voice == "en-US-AriaNeural":
            preset["voice"] = preset.get("voice", prefs.voice)
        preset.setdefault("voice", prefs.voice)
        rate = prefs.rate if prefs.rate and prefs.rate != "+0%" else preset["rate"]
        pitch = prefs.pitch if prefs.pitch and prefs.pitch != "+0Hz" else preset["pitch"]
        return {
            "voice": preset["voice"],
            "rate": rate,
            "pitch": pitch,
            "volume": preset.get("volume", "+0%"),
            "style": style,
            "personality": prefs.personality,
            "personality_prompt": PERSONALITIES.get(prefs.personality, PERSONALITIES["default"]),
        }

    def tts_params(self, user_id: str) -> Dict[str, str]:
        return self.apply_style(self.prefs_for(user_id))

    def wake_detect(self, transcript: str, phrase: str = "hey salar") -> bool:
        target = normalize(phrase)
        if not target:
            return False
        return target in normalize(transcript)

    def wake_matches(self, user_id: str, transcript: str) -> bool:
        prefs = self.prefs_for(user_id)
        return self.wake_detect(transcript, prefs.wake_phrase)

    def wake_variant(self, phrase: str) -> str:
        n = normalize(phrase)
        if n in WAKE_VARIANTS:
            return WAKE_VARIANTS[n]
        return phrase
