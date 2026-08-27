"""
NVIDIA NIM provider — OpenAI-compatible chat / streaming / tool-calling client.

Server-side only: the API key lives in settings (SALAR_NIM_API_KEY) and is
never sent to the browser.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0


class NIMError(Exception):
    """Normalized NIM error. keep .kind to allow policy-based fallback."""
    def __init__(self, message: str, kind: str = "upstream", status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind          # upstream|timeout|unavailable|rate_limited|auth
        self.status = status


class NIMProvider:
    def __init__(self, api_key: str, base_url: str = "https://integrate.api.nvidia.com/v1"):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(_DEFAULT_TIMEOUT, connect=10.0),
        )

    # ------------------------------------------------------------------ #
    async def list_models(self) -> List[str]:
        """Return provider model ids NIM reports available."""
        try:
            r = await self._client.get("/models")
            r.raise_for_status()
            data = r.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            log.warning("NIM list_models failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    async def chat(self, model: str, messages: List[Dict[str, Any]],
                   tools: Optional[List[Dict]] = None,
                   stream: bool = False,
                   extra: Optional[Dict] = None) -> Dict[str, Any]:
        """Non-streaming chat (with optional tools). Returns OpenAI-style JSON."""
        body: Dict[str, Any] = {"model": model, "messages": messages, "stream": False}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if extra:
            body.update(extra)
        try:
            r = await self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise NIMError("NIM request timed out", kind="timeout") from e
        except httpx.ConnectError as e:
            raise NIMError("NIM unreachable", kind="unavailable") from e
        if r.status_code == 429:
            raise NIMError("NIM rate-limited", kind="rate_limited", status=429)
        if r.status_code in (401, 403):
            raise NIMError("NIM authentication failed", kind="auth", status=r.status_code)
        if r.status_code >= 500:
            raise NIMError(f"NIM server error {r.status_code}", kind="upstream", status=r.status_code)
        if r.status_code != 200:
            raise NIMError(f"NIM error {r.status_code}: {r.text[:200]}",
                           kind="upstream", status=r.status_code)
        return r.json()

    # ------------------------------------------------------------------ #
    async def chat_stream(self, model: str, messages: List[Dict[str, Any]],
                          tools: Optional[List[Dict]] = None,
                          extra: Optional[Dict] = None) -> AsyncIterator[str]:
        """Stream text tokens from NIM (OpenAI-style SSE)."""
        body: Dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if extra:
            body.update(extra)
        async with self._client.stream("POST", "/chat/completions", json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content

    # ------------------------------------------------------------------ #
    async def embed(self, model: str, texts: List[str]) -> List[List[float]]:
        """Embeddings (OpenAI-compatible /embeddings)."""
        r = await self._client.post("/embeddings",
                                     json={"model": model, "input": texts, "truncate": "END"})
        r.raise_for_status()
        data = r.json()
        return [d["embedding"] for d in data.get("data", [])]

    # ------------------------------------------------------------------ #
    async def close(self):
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Gemini ↔ OpenAI tool-schema translation
# ---------------------------------------------------------------------------

def gemini_decl_to_openai_tools(declarations: List[Dict]) -> List[Dict]:
    """
    Convert Gemini `function_declarations` → OpenAI `tools` format.
    declarations item: {"name": "...", "description": "...", "parameters": {...}}
    """
    openai_tools = []
    for d in declarations:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": d["name"],
                "description": d.get("description", ""),
                "parameters": d.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools
