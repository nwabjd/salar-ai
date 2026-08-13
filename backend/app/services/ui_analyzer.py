# backend/app/services/ui_analyzer.py
import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_UI_PROMPT = (
    "You are a senior frontend engineer reviewing a screenshot of a user interface.\n"
    "Return ONLY a JSON object with this exact shape:\n"
    '{{"layout": "description of layout structure", "typography": ["font observations"], '
    '"colors": {"primary": "...", "secondary": "...", "background": "..."}, '
    '"components": [{{"type": "button/card/nav/etc", "location": "top-left etc", "notes": "..."}}], '
    '"animations": ["observations"], '
    '"implementation_suggestions": ["concrete code-level changes to reproduce this UI"]}}\n'
    "Focus on concrete, actionable observations a developer can act on."
)


class UIAnalyzer:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/png") -> Dict[str, Any]:
        if self._gemini is None:
            return {"status": "unavailable", "detail": "vision model not configured"}
        text = await self._gemini.chat_with_image(_UI_PROMPT, image_bytes, mime_type)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"layout": text, "typography": [], "colors": {}, "components": [], "animations": [], "implementation_suggestions": []}
        data["status"] = "ok"
        return data
