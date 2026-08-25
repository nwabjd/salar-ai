import json
import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)


async def ollama_chat(
    messages: List[Dict[str, str]],
    model: str = "",
    base_url: str = "http://127.0.0.1:11434",
    stream: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Stream a chat completion from local Ollama server."""
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"Ollama error {resp.status_code}: {body[:500]}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    yield delta
                if chunk.get("done"):
                    return


async def ollama_generate(
    prompt: str,
    model: str = "",
    base_url: str = "http://127.0.0.1:11434",
    system: str = "",
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Non-streaming generate from Ollama."""
    url = f"{base_url.rstrip('/')}/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:500]}")
        return resp.json().get("response", "")


async def list_ollama_models(base_url: str = "http://127.0.0.1:11434") -> List[str]:
    """List models available on the local Ollama server."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]


async def ollama_is_available(base_url: str = "http://127.0.0.1:11434") -> bool:
    """Check if Ollama server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
