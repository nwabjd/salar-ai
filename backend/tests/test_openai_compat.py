# tests/test_openai_compat.py
"""Unit tests for the OpenAI-compatible primary LLM client (`OpenAICompatClient`).

Verifies the Gemini<->OpenAI translation layer (roles, tool calls, function
responses), tool-schema conversion, retry/rate-limit behavior, and the vision
fallback delegation. No real network calls — httpx.MockTransport is used.
"""
import asyncio
import json

import httpx
import pytest

from app.services.gemini import GeminiBusyError
from app.services.openai_compat import OpenAICompatClient


def _client(handler, vision=None):
    transport = httpx.MockTransport(handler)
    return OpenAICompatClient(
        api_key="testkey",
        base_url="https://llm.test/v1",
        model="model-x",
        vision=vision,
        transport=transport,
    )


def _ok_choice(message=None, finish_reason="stop"):
    return {
        "choices": [{"message": message if message is not None else {"content": "hi"}, "finish_reason": finish_reason}]
    }


def _run(coro):
    return __import__("asyncio").new_event_loop().run_until_complete(coro)


def test_chat_translates_roles_and_returns_content():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_choice({"content": "  Groq reply  "}))

    client = _client(handler)
    result = _run(client.chat([
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "old"},
    ]))
    assert result == "Groq reply"
    msgs = captured["body"]["messages"]
    assert msgs == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "old"},
    ]
    assert captured["body"]["model"] == "model-x"
    child = client._client  # noqa: SLF001
    _run(child.aclose())


def test_chat_with_tools_converts_declarations_and_parses_calls():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_choice({
            "content": "",
            "tool_calls": [
                {
                    "id": "fc_1",
                    "type": "function",
                    "function": {"name": "open_app", "arguments": '{"app_name": "notepad"}'},
                }
            ],
        }, finish_reason="tool_calls"))

    client = _client(handler)
    tools = [{
        "function_declarations": [{
            "name": "open_app",
            "description": "Open an app",
            "parameters": {"type": "object", "properties": {"app_name": {"type": "string"}}},
        }]
    }]
    result = _run(client.chat_with_tools(
        [{"role": "user", "content": "open notepad"}], tools
    ))
    assert result == {
        "text": "",
        "function_calls": [{"name": "open_app", "args": {"app_name": "notepad"}}],
        "finish_reason": "tool_calls",
    }
    body = captured["body"]
    assert body["tools"][0]["type"] == "function"
    assert body["tools"][0]["function"]["name"] == "open_app"
    assert body["tool_choice"] == "auto"
    child = client._client
    _run(child.aclose())


def test_function_call_response_round_trip_translates_to_tool_messages():
    """Gemini functionCall/functionResponse parts -> OpenAI tool_calls + tool msgs."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_choice({"content": "done"}))

    client = _client(handler)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "run it"},
        {"role": "model", "content": [{"functionCall": {"name": "run_command", "args": {"command": "echo hi"}}}]},
        {"role": "user", "content": [{"functionResponse": {"name": "run_command", "response": {"stdout": "hi"}}}]},
    ]
    _run(client.chat(messages))
    oai = captured["body"]["messages"]
    assert oai[0] == {"role": "system", "content": "sys"}
    assert oai[1] == {"role": "user", "content": "run it"}
    assert oai[2]["role"] == "assistant"
    assert oai[2]["tool_calls"][0]["function"]["name"] == "run_command"
    tool_id = oai[2]["tool_calls"][0]["id"]
    assert oai[3] == {"role": "tool", "tool_call_id": tool_id, "content": json.dumps({"stdout": "hi"})}
    child = client._client
    _run(child.aclose())


def test_retry_then_success_on_429():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=_ok_choice({"content": "recovered"}))

    client = _client(handler)
    assert _run(client.chat([{"role": "user", "content": "x"}])) == "recovered"
    assert calls["n"] >= 3
    child = client._client
    _run(child.aclose())


def test_exhausted_retries_raise_gemini_busy(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = _client(handler)

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    with pytest.raises(GeminiBusyError, match="429"):
        _run(client.chat([{"role": "user", "content": "x"}]))
    child = client._client
    _run(child.aclose())


def test_parse_failed_400_is_retried_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(
                400, json={"error": {"message": "Parsing failed. The model generated output that could not be parsed."}}
            )
        return httpx.Response(200, json=_ok_choice({"content": "ok after retry"}))

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    client = _client(handler)
    result = _run(client.chat_with_tools([{"role": "user", "content": "x"}], [
        {"function_declarations": [{"name": "a", "description": "d", "parameters": {"type": "object", "properties": {}}}]}
    ]))
    assert result["text"] == "ok after retry"
    assert calls["n"] == 3
    child = client._client
    _run(child.aclose())


def test_failover_to_alternate_on_busy(monkeypatch):
    primary_calls = {"n": 0}

    def primary_handler(request: httpx.Request) -> httpx.Response:
        primary_calls["n"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    def alt_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_choice({"content": "alt answer"}))

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    alt = _client(alt_handler)
    primary = OpenAICompatClient(
        api_key="k", base_url="https://llm.test/v1", model="m",
        alternates=[alt], transport=httpx.MockTransport(primary_handler), retries=6,
    )
    result = _run(primary.chat([{"role": "user", "content": "x"}]))
    assert result == "alt answer"
    assert primary_calls["n"] == 6
    _run(primary.close())


def test_tool_call_failover_to_alternate(monkeypatch):
    def primary_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    def alt_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_choice({"content": "alt tools answer"}))

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    alt = _client(alt_handler)
    primary = OpenAICompatClient(
        api_key="k", base_url="https://llm.test/v1", model="m",
        alternates=[alt], transport=httpx.MockTransport(primary_handler), retries=2,
    )
    result = _run(primary.chat_with_tools([{"role": "user", "content": "go"}], [
        {"function_declarations": [{"name": "t", "description": "d", "parameters": {"type": "object", "properties": {}}}]}
    ]))
    assert result["text"] == "alt tools answer"
    assert result["function_calls"] == []
    _run(primary.close())


def test_http_4xx_does_not_failover():
    alt_called = {"n": 0}

    def primary_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad schema"}})

    def alt_handler(request: httpx.Request) -> httpx.Response:
        alt_called["n"] += 1
        return httpx.Response(200, json=_ok_choice({"content": "should not happen"}))

    alt = _client(alt_handler)
    primary = OpenAICompatClient(
        api_key="k", base_url="https://llm.test/v1", model="m",
        alternates=[alt], transport=httpx.MockTransport(primary_handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        _run(primary.chat([{"role": "user", "content": "x"}]))
    assert alt_called["n"] == 0
    _run(primary.close())


def test_chat_tool_use_error_retries_with_instruction():
    calls = {"n": 0}
    second_messages = {}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                400, json={"error": {"message": "Tool choice is none, but model called a tool", "code": "tool_use_failed"}}
            )
        second_messages["msgs"] = json.loads(request.content)["messages"]
        return httpx.Response(200, json=_ok_choice({"content": "handled"}))

    client = _client(handler)
    result = _run(client.chat([{"role": "user", "content": "What time is it? Use get_current_time."}]))
    assert result == "handled"
    assert calls["n"] == 2
    assert "No tools are available" in second_messages["msgs"][0]["content"]
    child = client._client
    _run(child.aclose())


def test_chat_tool_use_error_fails_over_to_alternate(monkeypatch):
    primary_calls = {"n": 0}
    alt_called = {"n": 0}

    def primary_handler(request: httpx.Request) -> httpx.Response:
        primary_calls["n"] += 1
        return httpx.Response(
            400, json={"error": {"message": "Tool choice is none, but model called a tool", "code": "tool_use_failed"}}
        )

    def alt_handler(request: httpx.Request) -> httpx.Response:
        alt_called["n"] += 1
        return httpx.Response(200, json=_ok_choice({"content": "alt plain answer"}))

    async def _no_sleep(_s):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    alt = _client(alt_handler)
    primary = OpenAICompatClient(
        api_key="k", base_url="https://llm.test/v1", model="m",
        alternates=[alt], transport=httpx.MockTransport(primary_handler), retries=2,
    )
    result = _run(primary.chat([{"role": "user", "content": "Open notepad for me"}]))
    assert result == "alt plain answer"
    assert primary_calls["n"] == 2
    assert alt_called["n"] == 1
    _run(primary.close())


def test_vision_delegates_and_raises_without_fallback():
    class FakeVision:
        def __init__(self):
            self.called = None

        async def chat_with_image(self, prompt, image_bytes, mime_type):
            self.called = (prompt, mime_type)
            return "see it"

    vision = FakeVision()
    client = _client(lambda r: httpx.Response(500, json={}), vision=vision)
    result = _run(client.chat_with_image("look", b"123", "image/png"))
    assert result == "see it"
    assert vision.called == ("look", "image/png")
    child = client._client
    _run(child.aclose())

    bare = _client(lambda r: httpx.Response(500, json={}))
    with pytest.raises(RuntimeError, match="no vision fallback"):
        _run(bare.chat_with_image("look", b"123"))
    child = bare._client
    _run(child.aclose())