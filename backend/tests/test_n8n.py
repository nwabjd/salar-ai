# tests/test_n8n.py
"""Tests for the SALAR ↔ n8n integration (client, config, agent wiring)."""
import asyncio

import httpx
import pytest

from app.services import state
from app.services.n8n_client import N8NError, N8nClient, get_n8n_client, resolve_n8n_config


def _asyncio_run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


WEBHOOK_WORKFLOW = {
    "id": "wf-1",
    "name": "Publish to Slack",
    "active": True,
    "activeVersionId": "v1",
    "isArchived": False,
    "triggerCount": 1,
    "tags": [{"id": "t1", "name": "marketing"}],
    "nodes": [
        {
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "parameters": {"path": "salar-run", "httpMethod": "POST"},
        },
        {"name": "Slack", "type": "n8n-nodes-base.slack"},
    ],
    "connections": {},
}

SCHEDULE_WORKFLOW = {
    "id": "wf-2",
    "name": "Nightly Digest",
    "active": False,
    "activeVersionId": None,
    "isArchived": False,
    "triggerCount": 1,
    "tags": [],
    "nodes": [{"name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger"}],
    "connections": {},
}

EXECUTION_SUCCESS = {
    "id": "7",
    "status": "success",
    "mode": "webhook",
    "finished": True,
    "workflowId": "wf-1",
    "startedAt": "2026-09-26T10:00:00.000Z",
    "stoppedAt": "2026-09-26T10:00:03.000Z",
    "data": {
        "result_data": {
            "lastNodeExecuted": "Slack",
            "runData": {
                "Slack": [
                    {
                        "data": {
                            "main": [
                                [
                                    {
                                        "json": {
                                            "ok": True,
                                            "channels": ["general"],
                                            "message": "hello",
                                        }
                                    }
                                ]
                            ]
                        }
                    }
                ]
            },
        }
    },
}


@pytest.fixture(autouse=True)
def _clean_n8n_state(monkeypatch):
    monkeypatch.delenv("SALAR_N8N_BASE_URL", raising=False)
    monkeypatch.delenv("SALAR_N8N_API_KEY", raising=False)
    state.n8n_connections.pop("u1", None)
    state.n8n_connections.pop("u2", None)
    yield


# ---------------------------------------------------------------- config


def test_resolve_config_from_env(monkeypatch):
    monkeypatch.setenv("SALAR_N8N_BASE_URL", "http://127.0.0.1:5678")
    monkeypatch.setenv("SALAR_N8N_API_KEY", "secret-key")
    cfg = resolve_n8n_config("u1")
    assert cfg == {"base_url": "http://127.0.0.1:5678", "api_key": "secret-key"}


def test_resolve_config_per_user_wins_over_env(monkeypatch):
    monkeypatch.setenv("SALAR_N8N_BASE_URL", "http://env:5678")
    monkeypatch.setenv("SALAR_N8N_API_KEY", "env-key")
    state.n8n_connections["u1"] = {"base_url": "http://user:5678", "api_key": "user-key"}
    cfg = resolve_n8n_config("u1")
    assert cfg == {"base_url": "http://user:5678", "api_key": "user-key"}
    # Other users still fall back to env.
    assert resolve_n8n_config("u2") == {"base_url": "http://env:5678", "api_key": "env-key"}


def test_resolve_config_none_when_unconfigured():
    assert resolve_n8n_config("u1") is None
    assert get_n8n_client("u1") is None


# --------------------------------------------------------------- client


def _transport(handler):
    return httpx.MockTransport(handler)


def test_list_workflows_maps_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/workflows"
        return httpx.Response(200, json={"data": [WEBHOOK_WORKFLOW, SCHEDULE_WORKFLOW], "nextCursor": None})

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    result = _asyncio_run(client.list_workflows())
    assert result["count"] == 2
    wf = result["workflows"][0]
    assert wf["id"] == "wf-1"
    assert wf["active"] is True
    assert wf["tags"] == ["marketing"]
    assert wf["webhook_triggers"] == [{"node": "Webhook", "path": "salar-run", "http_method": "POST"}]
    assert "webhook_triggers" not in result["workflows"][1]


def test_list_workflows_sends_filters():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("active") == "true"
        assert request.url.params.get("limit") == "25"
        return httpx.Response(200, json={"data": [], "nextCursor": None})

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    _asyncio_run(client.list_workflows(active=True, limit=25))


def test_trigger_via_webhook():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/workflows/wf-1":
            return httpx.Response(200, json=WEBHOOK_WORKFLOW)
        if request.url.path == "/webhook/salar-run":
            assert request.method == "POST"
            assert request.read() == b'{"key":"value"}'
            return httpx.Response(200, json={"started": True})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    result = _asyncio_run(client.trigger_workflow("wf-1", {"key": "value"}))
    assert result["triggered"] == "webhook"
    assert result["webhook_url"] == "http://127.0.0.1:5678/webhook/salar-run"
    assert result["http_method"] == "POST"
    assert result["status_code"] == 200


def test_trigger_falls_back_to_executions_api():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/workflows/wf-2":
            return httpx.Response(200, json=SCHEDULE_WORKFLOW)
        if request.url.path == "/api/v1/executions" and request.method == "POST":
            body = request.read()
            assert b'"workflowId":"wf-2"' in body
            return httpx.Response(200, json={"executionId": "99", "status": "success"})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    result = _asyncio_run(client.trigger_workflow("wf-2", {}))
    assert result["triggered"] == "execution_api"
    assert result["execution_id"] == "99"


def test_trigger_without_webhook_or_execution_endpoint_fails_helpfully():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/workflows/wf-2":
            return httpx.Response(200, json=SCHEDULE_WORKFLOW)
        if request.url.path == "/api/v1/executions" and request.method == "POST":
            return httpx.Response(405, json={"message": "not allowed"})
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    with pytest.raises(N8NError) as exc_info:
        _asyncio_run(client.trigger_workflow("wf-2", {}))
    assert "Webhook trigger" in str(exc_info.value)


def test_get_execution_summary_and_outputs():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/executions/7"
        assert request.url.params.get("includeData") == "true"
        return httpx.Response(200, json=EXECUTION_SUCCESS)

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    result = _asyncio_run(client.get_execution("7"))
    assert result["status"] == "success"
    assert result["workflow_id"] == "wf-1"
    outputs = result["outputs"]
    assert outputs["last_node_executed"] == "Slack"
    assert '"message": "hello"' in outputs["node_outputs"]["Slack"]


def test_auth_error_kind():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid API Key"})

    client = N8nClient("http://127.0.0.1:5678", "k", transport=_transport(handler))
    with pytest.raises(N8NError) as exc_info:
        _asyncio_run(client.list_workflows())
    assert exc_info.value.kind == "auth"


def test_health_connected_and_failure():
    ok_client = N8nClient(
        "http://127.0.0.1:5678",
        "k",
        transport=_transport(lambda r: httpx.Response(200, json={"data": [], "nextCursor": None})),
    )
    assert _asyncio_run(ok_client.health())["connected"] is True

    bad_client = N8nClient(
        "http://127.0.0.1:5678",
        "k",
        transport=_transport(lambda r: httpx.Response(401, json={})),
    )
    health = _asyncio_run(bad_client.health())
    assert health["connected"] is False
    assert "auth" in health["error"]


# ---------------------------------------------------------------- agent wiring


def test_agent_exposes_n8n_tools():
    from app.services.agent import TOOL_DEFINITIONS, execute_tool

    all_decls = [d for g in TOOL_DEFINITIONS for d in g.get("function_declarations", [])]
    names = {d["name"] for d in all_decls}
    assert {
        "n8n_instance_info",
        "n8n_list_workflows",
        "n8n_execute_workflow",
        "n8n_workflow_result",
    } <= names

    # Unconfigured instance -> clean error dict, not an exception.
    result = _asyncio_run(execute_tool("n8n_instance_info", {}, "u1"))
    assert "error" in result
    assert "configured" in result["error"]

    result = _asyncio_run(execute_tool("n8n_execute_workflow", {"workflow_id": "wf-1"}, "u1"))
    assert "error" in result


def test_mcp_server_serves_n8n_tools():
    from app.mcp_server import build_tool_specs

    specs = build_tool_specs()
    assert {s["name"] for s in specs} >= {
        "n8n_instance_info",
        "n8n_list_workflows",
        "n8n_execute_workflow",
        "n8n_workflow_result",
    }
