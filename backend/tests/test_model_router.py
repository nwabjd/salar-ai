from app.services.model_router import ModelRouter, ModelRouterError

import pytest


def test_light_default():
    r = ModelRouter()
    assert r.route("what time is it") == "gemini-3.1-flash-lite"


def test_code_detection():
    r = ModelRouter()
    assert r.route("debug this python traceback: def foo():") == "gemini-3.1-flash-lite"


def test_vision_content_type():
    r = ModelRouter()
    assert r.route("explain this error", content_type="screenshot") == "gemini-3.1-pro-vision"


def test_vision_keyword():
    r = ModelRouter()
    assert r.route("what is wrong in this screenshot?") == "gemini-3.1-pro-vision"


def test_voice_content_type():
    r = ModelRouter()
    assert r.route("respond aloud", content_type="voice") == "gemini-3.1-flash-live-preview"


def test_research():
    r = ModelRouter()
    assert r.route("do deep research and compare sources") == "gemini-3.1-pro"


def test_reasoning_complexity():
    r = ModelRouter()
    assert r.route("explain deeply and analyze tradeoffs", complexity="complex") == "gemini-3.1-pro"


def test_creative():
    r = ModelRouter()
    assert r.route("draft a creative ad concept") == "gemini-3.1-pro"


def test_route_for_tools_code():
    r = ModelRouter()
    assert r.route_for_tools(["run_command", "list_files"], "run my build") == "gemini-3.1-flash-lite"


def test_route_for_tools_vision():
    r = ModelRouter()
    assert r.route_for_tools(["screenshot"], "what is this") == "gemini-3.1-pro-vision"


def test_capabilities_shape():
    r = ModelRouter()
    caps = r.capabilities()
    assert "code" in caps
    assert "vision" in caps
    assert isinstance(caps["code"], list)
