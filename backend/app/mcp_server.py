"""SALAR MCP server (stdio transport).

Exposes SALAR's full agent tool set as Model Context Protocol tools so any
MCP client can drive SALAR directly — OpenCode, Claude Desktop, Cursor,
OpenClaw, the ``mcp`` CLI, or a custom script.

Run (from the ``backend`` directory, inside the backend virtualenv):

    python -m app.mcp_server [--user-id <salar-user-id>]

Identity: SALAR tools act on behalf of a single user. Prefer
``SALAR_MCP_USER_ID`` (or ``--user-id``); when unset the server resolves the
first user in the database (usually the bootstrap/owner account) lazily on
each tool call — the server itself always starts, so ``tools/list`` works
even against a not-yet-seeded database, and tool calls report a clear error
until a user is available.

Note: tools that require the desktop app (``run_command``, ``list_files``,
device routing, ...) work when this server runs on the same machine as a
connected SALAR desktop device, mirroring how the backend executes those
same tools. Tools that do not touch the device (``save_memory``, ``search_*``,
``email_*``, ``create_task``, ...) work anywhere the backend DB/credentials do.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

SERVER_NAME = "salar-mcp"
log = logging.getLogger(__name__)


def build_tool_specs() -> List[Dict[str, Any]]:
    """Flatten TOOL_DEFINITIONS (Gemini function-declaration format) into MCP tool specs."""
    from .services.agent import TOOL_DEFINITIONS

    specs: List[Dict[str, Any]] = []
    for group in TOOL_DEFINITIONS:
        for decl in group.get("function_declarations", []):
            name = decl.get("name")
            if not name:
                continue
            params = decl.get("parameters") or {}
            schema = json.loads(json.dumps(params)) if params else {}
            schema.setdefault("type", "object")
            schema.setdefault("properties", {})
            schema.setdefault("additionalProperties", False)
            specs.append(
                {"name": name, "description": decl.get("description", ""), "inputSchema": schema}
            )
    return specs


def _settings() -> Any:
    from .config import Settings

    return Settings()


_resolved_user_id: Optional[str] = None  # module-level cache for per-call resolution


def resolve_user_id(explicit: Optional[str] = None) -> Optional[str]:
    """Pick the SALAR user identity MCP tool calls act on behalf of.

    Returns ``None`` (never raises) when no user can be determined — tool
    calls then report a clear error instead of the server failing to start.
    """
    global _resolved_user_id
    if explicit or os.environ.get("SALAR_MCP_USER_ID") or _settings().mcp_user_id:
        return explicit or os.environ.get("SALAR_MCP_USER_ID") or _settings().mcp_user_id
    if _resolved_user_id is None:
        _resolved_user_id = _first_user_id()
    return _resolved_user_id


def _first_user_id() -> Optional[str]:
    from sqlalchemy import select

    from .models import User
    from .services.agent import get_db_session

    gen = get_db_session("")
    db = next(gen)
    try:
        row = db.execute(select(User).order_by(User.created_at.asc()).limit(1)).scalar_one_or_none()
        if row is None:
            log.warning("No SALAR user found to run MCP tools; set SALAR_MCP_USER_ID")
            return None
        log.info("MCP server acting as user %s", row.id)
        return row.id
    except Exception as exc:  # noqa: BLE001 — DB migrations may be pending (e.g. missing tables)
        log.warning("Could not resolve a SALAR user for MCP (%s); set SALAR_MCP_USER_ID", exc)
        return None
    finally:
        gen.close()


def _is_admin(user_id: str, db: Any) -> bool:
    try:
        from sqlalchemy import select

        from .models import User

        row = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        return bool(row and row.is_admin)
    except Exception:  # noqa: BLE001 — treat unknown users as non-admin
        return False


async def run_salar_tool(name: str, args: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Execute one SALAR agent tool with the same semantics as the chat/agent APIs."""
    from .services.agent import execute_tool, get_db_session

    gen = get_db_session(user_id)
    db = next(gen)
    try:
        settings = _settings()
        return await execute_tool(
            name,
            args,
            user_id,
            db,
            is_admin=_is_admin(user_id, db),
            base_url=settings.public_api_url,
            jwt_secret=settings.jwt_secret,
        )
    finally:
        gen.close()


def _json_text(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except TypeError:
        return str(obj)


def _as_tool(spec: Dict[str, Any]) -> Tool:
    return Tool(name=spec["name"], description=spec["description"], inputSchema=spec["inputSchema"])


def make_server(specs: Sequence[Dict[str, Any]], user_id_fn) -> Server:
    server = Server(SERVER_NAME)

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        return [_as_tool(s) for s in specs]

    @server.call_tool()
    async def call_tool(name: str, arguments: Optional[Dict[str, Any]]) -> CallToolResult:
        user_id = user_id_fn()
        if not user_id:
            return CallToolResult(
                content=[TextContent(type="text", text=_json_text({"error": "No SALAR user available to act as. Set SALAR_MCP_USER_ID or seed the database (run the backend once)."}))],
                isError=True,
            )
        result = await run_salar_tool(name, arguments or {}, user_id)
        is_error = bool(result.get("error") or result.get("exception"))
        return CallToolResult(content=[TextContent(type="text", text=_json_text(result))], isError=is_error)

    return server


async def amain(explicit_user_id: Optional[str] = None) -> None:
    logging.basicConfig(level=os.environ.get("SALAR_LOG_LEVEL", "INFO"))
    specs = build_tool_specs()
    user_fn = lambda: resolve_user_id(explicit_user_id)
    resolved = user_fn()
    log.info("Starting SALAR MCP server with %d tools (user: %s)", len(specs), resolved or "unresolved")
    server = make_server(specs, user_fn)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="salar-mcp", description="SALAR MCP server (stdio)")
    parser.add_argument(
        "--user-id", default=None, help="SALAR user id tools act as (default: SALAR_MCP_USER_ID or first user)"
    )
    parser.add_argument("--list-tools", action="store_true", help="Print exposed tool names and exit")
    args = parser.parse_args(argv)
    if args.list_tools:
        for spec in build_tool_specs():
            print(f"{spec['name']}: {spec['description'][:100]}")
        return
    asyncio.run(amain(args.user_id))


if __name__ == "__main__":
    main()