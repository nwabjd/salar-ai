# backend/app/services/image_gen.py
import base64
import logging
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger(__name__)

IMAGEN_MODEL = "imagen-3.0-generate-001"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class ImageGenerator:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key

    async def generate(self, prompt: str, *, count: int = 1, aspect_ratio: str = "1:1") -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "unavailable", "detail": "no gemini api key configured"}
        body = {
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": count, "aspectRatio": aspect_ratio},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{_API_BASE}/{IMAGEN_MODEL}:predict",
                    params={"key": self.api_key},
                    json=body,
                )
                r.raise_for_status()
                data = r.json()
            images = []
            for pred in data.get("predictions", []):
                b64 = pred.get("bytesBase64Encoded")
                if b64:
                    images.append(base64.b64decode(b64))
            if not images:
                return {"status": "error", "detail": "no images returned"}
            return {"status": "ok", "images": images, "count": len(images), "prompt": prompt}
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}
