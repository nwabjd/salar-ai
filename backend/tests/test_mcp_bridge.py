# tests/test_mcp_bridge.py
"""Tests for the SALAR ↔ MCP bridge (client + server directions)."""
import json
import os
import sys

import pytest

from app.services.mcp_bridge import (
    mcp_call_tool,
    mcp_list_tools,
    parse_server_config,
)


def _mini_server_script() -> str:
    """A tiny stdio MCP server exposing one tool, used for a real round trip."""
    return (
        "from mcp.server.fastmcp import FastMCP\n"
        "mcp = FastMCP('mini')\n"
        "@mcp.tool()\n"
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        "mcp.run()\n"
    )


# ---------------------------------------------------------------- config parsing


def test_parse_server_config_list():
    raw = json.dumps(
        [
            {"name": "github", "command": "npx", "args": ["-y", "server-github"], "env": {"TOKEN": "abc"}},
            {"name": "fs", "command": "python", "args": ["-m", "mcp_server_fs"]},
        ]
    )
    servers = parse_server_config(raw)
    assert [s["name"] for s in servers] == ["github", "fs"]
    assert servers[0]["args"] == ["-y", "server-github"]
    assert servers[0]["env"] == {"TOKEN": "abc"}
    assert servers[1]["env"] == {}


def test_parse_server_config_dict_form():
    raw = json.dumps({"github": {"command": "npx", "args": ["-y", "server-github"]}})
    servers = parse_server_config(raw)
    assert servers == [{"name": "github", "command": "npx", "args": ["-y", "server-github"], "env": {}}]


@pytest.mark.parametrize("bad", ["", "   ", "not json", "42", '{"a": 1}'])
def test_parse_server_config_invalid_is_clean(bad):
    assert parse_server_config(bad) == []


def test_parse_server_config_skips_broken_entries():
    raw = json.dumps(
        [
            {"name": "good", "command": "python"},
            {"command": "no-name"},
            {"name": "no-command"},
            "junk",
        ]
    )
    servers = parse_server_config(raw)
    assert [s["name"] for s in servers] == ["good"]


# ---------------------------------------------------------------- agent wiring


def test_execute_tool_exposes_mcp_tools():
    from app.services.agent import TOOL_DEFINITIONS, execute_tool

    all_decls = [d for g in TOOL_DEFINITIONS for d in g.get("function_declarations", [])]
    names = {d["name"] for d in all_decls}
    assert {"mcp_tools", "mcp_call"} <= names

    # Unknown server → clean error dict, not an exception (db_session is None here).
    result = asyncio_run(execute_tool("mcp_tools", {"server": "ghost"}, "u1"))
    assert "error" in result
    assert "ghost" in result["error"]

    result = asyncio_run(execute_tool("mcp_call", {"server": "ghost", "tool": "x", "arguments": {}}, "u1"))
    assert "error" in result


# ---------------------------------------------------------------- MCP server side


def test_salar_mcp_server_exposes_all_agent_tools():
    from app.services.agent import TOOL_DEFINITIONS
    from app.mcp_server import build_tool_specs

    specs = build_tool_specs()
    agent_names = {d["name"] for g in TOOL_DEFINITIONS for d in g.get("function_declarations", [])}
    assert {s["name"] for s in specs} == agent_names
    for spec in specs:
        assert spec["inputSchema"].get("type") == "object"
        assert "properties" in spec["inputSchema"]


def test_salar_mcp_server_list_tools():
    from app.mcp_server import _as_tool, build_tool_specs

    spec = next(s for s in build_tool_specs() if s["name"] == "run_command")
    tool = _as_tool(spec)
    assert tool.name == "run_command"
    assert tool.inputSchema["properties"]["command"]["type"] == "string"


# ---------------------------------------------------------------- real round trip


def test_client_round_trip_against_stdlib_server(monkeypatch):
    server_cfg = [{"name": "mini", "command": sys.executable, "args": ["-c", _mini_server_script()]}]
    monkeypatch.setenv("SALAR_MCP_SERVERS", json.dumps(server_cfg))

    tools = asyncio_run(mcp_list_tools("mini"))
    assert tools.get("count") == 1, tools
    assert tools["tools"][0]["name"] == "add"
    assert "inputSchema" in tools["tools"][0]

    result = asyncio_run(mcp_call_tool("mini", "add", {"a": 2, "b": 3}))
    assert "error" not in result or result["error"] is False, result
    text = "".join(c.get("text", "") for c in result["content"] if c.get("type") == "text")
    assert "5" in text


def asyncio_run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)