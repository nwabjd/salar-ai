# backend/app/services/vision.py
import base64
import io
import logging
from typing import Any, Dict, List, Optional

from PIL import Image

log = logging.getLogger(__name__)


class VisionService:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    def capture_screenshot(self) -> bytes:
        import mss
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    async def analyze_screenshot(self, prompt: str) -> Dict[str, Any]:
        png = self.capture_screenshot()
        return await self.analyze_image(png, prompt, mime_type="image/png")

    async def analyze_image(self, image_bytes: bytes, prompt: str, mime_type: str = "image/png") -> Dict[str, Any]:
        if self._gemini is None:
            return {"error": "vision model not configured", "status": "unavailable"}
        text = await self._gemini.chat_with_image(prompt, image_bytes, mime_type)
        return {"status": "ok", "answer": text}

    def describe_image(self, image_bytes: bytes, mime_type: str = "image/png") -> Dict[str, Any]:
        """Non-LLM fallback description (size, mode)."""
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return {"status": "ok", "width": img.width, "height": img.height, "mode": img.mode}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
