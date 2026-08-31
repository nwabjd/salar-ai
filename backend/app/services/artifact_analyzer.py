# backend/app/services/artifact_analyzer.py
import io
import json
import logging

from PIL import Image

log = logging.getLogger(__name__)

_IMAGE_PROMPT = (
    "Analyze this attachment (image) for the user's assistant memory.\n"
    "Return a concise JSON object with this exact shape:\n"
    '{"description": "2-3 sentence visual description", '
    '"key_points": ["bullet points of notable content"], '
    '"type": "image"}\n'
    "Only return valid JSON."
)

_TEXT_PROMPT = (
    "Analyze this attachment (text document) for the user's assistant memory.\n"
    "Return a concise JSON object with this exact shape:\n"
    '{"description": "1-2 sentence summary", '
    '"key_points": ["3-6 bullet points of key content"], '
    '"type": "text"}\n'
    "Only return valid JSON."
)

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_TEXT_EXT = {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css"}


class ArtifactAnalyzer:
    def __init__(self, gemini=None) -> None:
        self._gemini = gemini

    def _image_meta(self, content: bytes) -> dict:
        try:
            img = Image.open(io.BytesIO(content))
            return {"width": img.width, "height": img.height, "mode": img.mode}
        except Exception:
            return {}

    def _text_points(self, text: str, max_points: int = 6) -> dict:
        clean = " ".join(text.split())
        if not clean:
            return {"description": "", "key_points": []}
        words = clean.split(" ")
        summary = " ".join(words[:60]) + ("…" if len(words) > 60 else "")
        points = []
        step = max(1, len(words) // max_points)
        for i in range(0, len(words), step):
            if len(points) >= max_points:
                break
            start = i
            end = min(i + step, len(words))
            chunk = " ".join(words[start:end])
            if chunk:
                points.append(chunk)
        return {"description": summary, "key_points": points}

    async def analyze(self, ext: str, content: bytes, text: str = "") -> dict:
        ext = ext.lower()
        if ext in _IMAGE_EXT:
            if self._gemini is not None:
                try:
                    raw = await self._gemini.chat_with_image(
                        _IMAGE_PROMPT, content, "image/png" if ext == ".png" else "image/jpeg"
                    )
                    data = json.loads(raw)
                    data["status"] = "ok"
                    data["meta"] = self._image_meta(content)
                    return data
                except Exception as exc:
                    log.warning("Image analysis failed: %s", exc)
            data = self._text_points(content.decode("utf-8", errors="replace"))
            data["status"] = "ok"
            data["type"] = "image"
            data["meta"] = self._image_meta(content)
            return data
        if ext in _TEXT_EXT:
            if self._gemini is not None and text.strip():
                try:
                    raw = await self._gemini.chat(f"BEGIN CONTENT\n{text[:8000]}\nEND CONTENT\n\n{_TEXT_PROMPT}")
                    data = json.loads(raw)
                    data["status"] = "ok"
                    return data
                except Exception as exc:
                    log.warning("Text analysis failed: %s", exc)
            data = self._text_points(text[:12000] if text else "")
            data["status"] = "ok"
            data["type"] = "text"
            return data
        return {"status": "ok", "description": "", "key_points": [], "type": "document"}