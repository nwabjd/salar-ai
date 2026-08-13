# tests/test_vision_clipboard.py
import io
import json
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.services.clipboard_intel import ClipboardIntelligence
from app.services.browser_intel import BrowserIntelligence
from app.services.ui_analyzer import UIAnalyzer
from app.services.vision import VisionService


def _png_bytes():
    img = Image.new("RGB", (64, 48), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_vision_analyze_image():
    gemini = AsyncMock()
    gemini.chat_with_image = AsyncMock(return_value="I see a red image.")
    vs = VisionService(gemini=gemini)
    result = await vs.analyze_image(_png_bytes(), "what is this?")
    assert result["status"] == "ok"
    assert result["answer"] == "I see a red image."
    gemini.chat_with_image.assert_awaited_once()


@pytest.mark.asyncio
async def test_vision_no_model():
    result = await VisionService(gemini=None).analyze_image(_png_bytes(), "what?")
    assert result["status"] == "unavailable"


def test_vision_describe_fallback():
    d = VisionService().describe_image(_png_bytes())
    assert d["status"] == "ok"
    assert d["width"] == 64
    assert d["height"] == 48


def test_clipboard_classify_url():
    c = ClipboardIntelligence().classify("https://example.com/docs")
    assert c["kind"] == "url"
    assert "Summarize this page" in c["suggested_actions"]


def test_clipboard_classify_email():
    c = ClipboardIntelligence().classify("alice@example.com")
    assert c["kind"] == "email"


def test_clipboard_classify_text():
    c = ClipboardIntelligence().classify("hello world")
    assert c["kind"] == "text"


def test_clipboard_empty():
    c = ClipboardIntelligence().classify("  ")
    assert c["kind"] == "empty"


@pytest.mark.asyncio
async def test_browser_summarize_no_model():
    # Gemini=None -> returns first 500 chars as summary with a note.
    bi = BrowserIntelligence(gemini=None)
    result = await bi.summarize("https://example.com")
    # example.com may or may not be reachable; assert graceful handling either way.
    assert result["status"] in ("ok", "error")
    assert "url" in result


@pytest.mark.asyncio
async def test_ui_analyzer_structured():
    gemini = AsyncMock()
    gemini.chat_with_image = AsyncMock(return_value=json.dumps({
        "layout": "hero with navbar",
        "typography": ["sans-serif"],
        "colors": {"primary": "#000"},
        "components": [{"type": "button", "location": "center", "notes": "cta"}],
        "animations": [],
        "implementation_suggestions": ["use grid layout"],
    }))
    result = await UIAnalyzer(gemini=gemini).analyze(_png_bytes())
    assert result["status"] == "ok"
    assert result["layout"] == "hero with navbar"
    assert len(result["implementation_suggestions"]) == 1


@pytest.mark.asyncio
async def test_ui_analyzer_malformed_fallback():
    gemini = AsyncMock()
    gemini.chat_with_image = AsyncMock(return_value="raw text not json")
    result = await UIAnalyzer(gemini=gemini).analyze(_png_bytes())
    assert result["status"] == "ok"
    assert "raw text not json" in result["layout"]
