"""SALAR ↔ MCP (Model Context Protocol) bridge.

Two directions:

* SALAR as MCP *client* — SALAR's agent tools can call tools exposed by
  external MCP servers (GitHub, filesystem, browser, database, ...). Servers
  are stdio subprocesses configured with the ``SALAR_MCP_SERVERS`` env var:

      SALAR_MCP_SERVERS='[{"name":"github","command":"npx","args":["-y","@modelcontextprotocol/server-github"],"env":{"GITHUB_PERSONAL_ACCESS_TOKEN":"..."}}]'

  JSON can also be an object keyed by server name. Entries without a
  ``name`` + ``command`` are skipped. Agent tools ``mcp_tools`` and
  ``mcp_call`` drive these servers.

* SALAR as MCP *server* — see ``app/mcp_server.py`` (stdio server exposing
  SALAR's full agent tool set to any MCP client: OpenCode, Claude Desktop,
  Cursor, OpenClaw, the ``mcp`` CLI, ...).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger(__name__)

_LIST_TIMEOUT_S = 30.0
_CALL_TIMEOUT_S = 60.0


def parse_server_config(raw: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse the SALAR_MCP_SERVERS JSON into a normalized server list.

    Accepts either a JSON list of object entries or a JSON object keyed by
    server name. Invalid JSON (or unparseable entries) are skipped with a log
    line rather than raising, so a config typo degrades to "no external MCP
    servers" instead of breaking the agent.
    """
    if raw is None:
        raw = os.environ.get("SALAR_MCP_SERVERS", "[]")
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("SALAR_MCP_SERVERS is not valid JSON; ignoring external MCP servers")
        return []
    if isinstance(data, dict):
        data = [{"name": name, **(cfg if isinstance(cfg, dict) else {})} for name, cfg in data.items()]
    if not isinstance(data, list):
        log.warning("SALAR_MCP_SERVERS must be a JSON list or object; ignoring")
        return []
    servers: List[Dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        command = str(entry.get("command") or "").strip()
        if not name or not command:
            log.warning("SALAR_MCP_SERVERS entry missing name/command; skipping %r", entry)
            continue
        servers.append(
            {
                "name": name,
                "command": command,
                "args": [str(a) for a in (entry.get("args") or [])],
                "env": {str(k): str(v) for k, v in (entry.get("env") or {}).items()},
            }
        )
    return servers


def configured_server_names() -> List[str]:
    return [cfg["name"] for cfg in parse_server_config()]


def _find_server(name: str) -> Optional[Dict[str, Any]]:
    for cfg in parse_server_config():
        if cfg["name"] == name:
            return cfg
    return None


async def mcp_list_tools(server_name: str) -> Dict[str, Any]:
    """Return the tools advertised by an external MCP server (never raises)."""
    cfg = _find_server(server_name)
    if cfg is None:
        return {"error": f"Unknown MCP server '{server_name}'", "configured": configured_server_names()}
    try:
        tools = await asyncio.wait_for(_collect_tools(cfg), timeout=_LIST_TIMEOUT_S)
        return {"server": server_name, "count": len(tools), "tools": tools}
    except Exception as exc:  # noqa: BLE001 — surface cleanly to the agent
        log.exception("mcp_list_tools failed for %s", server_name)
        return {"server": server_name, "error": str(exc)}


async def mcp_call_tool(
    server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Call a tool on an external MCP server and return a JSON-safe result (never raises)."""
    cfg = _find_server(server_name)
    if cfg is None:
        return {"error": f"Unknown MCP server '{server_name}'", "configured": configured_server_names()}
    try:
        payload = await asyncio.wait_for(_call(cfg, tool_name, arguments or {}), timeout=_CALL_TIMEOUT_S)
        return {"server": server_name, "tool": tool_name, **payload}
    except Exception as exc:  # noqa: BLE001
        log.exception("mcp_call_tool failed: %s.%s", server_name, tool_name)
        return {"server": server_name, "tool": tool_name, "error": str(exc)}


async def _collect_tools(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    async with _session(cfg) as session:
        listed = await session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {"type": "object", "properties": {}},
            }
            for t in listed.tools
        ]


async def _call(cfg: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    async with _session(cfg) as session:
        result = await session.call_tool(tool_name, arguments)
        return _content_to_dict(result)


def _content_to_dict(result: Any) -> Dict[str, Any]:
    """Convert an MCP CallToolResult into a plain JSON-safe dict that a model can read."""
    payload: Dict[str, Any] = {"isError": bool(getattr(result, "isError", False))}
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payload["structuredContent"] = structured
    content: List[Dict[str, Any]] = []
    for item in result.content if result.content else []:
        itype = getattr(item, "type", "text")
        if itype == "text":
            content.append({"type": "text", "text": item.text})
        elif itype == "image":
            data = getattr(item, "data", "")
            content.append({"type": "image", "data": str(data)[:4000], "mimeType": getattr(item, "mimeType", "")})
        elif itype == "resource":
            content.append(
                {"type": "resource", "uri": getattr(item, "uri", ""), "mimeType": getattr(item, "mimeType", "")}
            )
        else:
            content.append({"type": itype, "text": str(item)[:2000]})
    if not content:
        content.append({"type": "text", "text": json.dumps(structured or payload, default=str)})
    payload["content"] = content
    return payload


@asynccontextmanager
async def _session(cfg: Dict[str, Any]) -> AsyncIterator[ClientSession]:
    """Start a stdio MCP server subprocess and yield a connected client session.

    The subprocess's environment is the parent's env (so PATH, SystemRoot
    etc. survive on Windows) merged with the server's own ``env`` overrides.
    """
    merged_env = {**os.environ, **cfg["env"]}
    params = StdioServerParameters(command=cfg["command"], args=cfg["args"], env=merged_env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session