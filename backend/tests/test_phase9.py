# tests/test_phase9.py
import json

import pytest
from fastapi.testclient import TestClient

from app.cli import build_parser
from app.sdk import SalarAPIError, SalarClient


def test_cli_parser_built():
    parser = build_parser()
    ns = parser.parse_args(["ping"])
    assert ns.command == "ping"


def test_cli_parser_search():
    ns = build_parser().parse_args(["search", "--query", "test", "--limit", "5"])
    assert ns.query == "test"
    assert ns.limit == 5


def test_sdk_error_on_http_error():
    # point at an unreachable port; requests should raise SalarAPIError or httpx error
    client = SalarClient("http://localhost:1")
    with pytest.raises(Exception):
        client.dashboard()
    client.close()


def test_sdk_headers():
    client = SalarClient("http://localhost:8000", token="abc123")
    headers = client._headers()
    assert headers["Authorization"] == "Bearer abc123"
    client.close()


def test_sdk_login_requires_token_field():
    class FakeResp:
        status_code = 200
        content = b'{"token": "t123"}'

        def json(self):
            return {"token": "t123"}

    import httpx
    original = httpx.Client.request

    def fake_request(self, method, path, **kwargs):
        return FakeResp()

    httpx.Client.request = fake_request
    try:
        client = SalarClient("http://localhost:8000")
        token = client.login("a@b.com", "pw")
        assert token == "t123"
    finally:
        httpx.Client.request = original
    client.close()


def test_sdk_chat_body_uses_content_and_conversation_id():
    captured = {}

    class FakeResp:
        status_code = 200
        content = b'{"user_message": {"id": "u1"}, "assistant_message": {"id": "a1"}}'

        def json(self):
            return {"user_message": {"id": "u1"}, "assistant_message": {"id": "a1"}}

    import httpx
    original = httpx.Client.request

    def fake_request(self, method, path, **kwargs):
        captured.update(method=method, path=path, json=kwargs.get("json"))
        return FakeResp()

    httpx.Client.request = fake_request
    try:
        client = SalarClient("http://localhost:8000")
        client.chat("hello", conversation_id="conv-1")
    finally:
        httpx.Client.request = original
    client.close()

    assert captured["path"] == "/api/chat"
    assert captured["json"] == {"conversation_id": "conv-1", "content": "hello"}


def test_dev_docs_endpoints_listing(client):
    r = client.get("/api/dev/endpoints")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    paths = [e["path"] for e in body["endpoints"]]
    assert "/api/health" in paths
    assert "/api/auth/me" in paths
    for e in body["endpoints"]:
        assert e["path"].startswith("/api")
        assert "{" not in e["path"]


def test_dev_docs_summary_groups_by_tag(client):
    r = client.get("/api/dev/summary")
    assert r.status_code == 200
    body = r.json()
    assert "authentication" in body["tags"]
    assert "chat" in body["groups"]
    assert any(g["path"] == "/api/chat" and g["method"] == "POST" for g in body["groups"]["chat"])
