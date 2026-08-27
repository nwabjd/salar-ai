"""
SALAAR Intelligence Orchestration endpoints — NVIDIA NIM backbone.

These endpoints expose the NIM provider, model registry, routing, and an
OpenAI-compatible chat/stream path. The API key never leaves the server.

ROUTING: Uses BenchmarkRouter for latency-aware, health-aware selection
based on real benchmark scores from the diagnostic.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..config import Settings
from ..services import model_registry
from ..services.model_router import BenchmarkRouter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nim", tags=["nim"])


def _settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or Settings()


def _provider(request: Request):
    return getattr(request.app.state, "nim", None)


def _require_provider(request: Request):
    provider = _provider(request)
    if provider is None:
        raise HTTPException(status_code=503, detail="NVIDIA NIM is not configured")
    return provider


def _nip_router():
    return BenchmarkRouter()


@router.get("/status")
async def status(request: Request):
    provider = _provider(request)
    if provider is None:
        return {
            "configured": False,
            "enabled": False,
        }
    models = await provider.list_models()
    return {
        "configured": True,
        "enabled": bool(getattr(_settings(request), "nim_enabled", True)),
        "models_available": len(models),
        "default_model": getattr(_settings(request), "nim_default_model", None),
    }


@router.get("/models")
async def nim_models(request: Request):
    """Full model registry (local metadata) + live provider availability."""
    provider = _require_provider(request)
    available = set(await provider.list_models())
    specs = []
    for spec in model_registry.MODELS.values():
        if spec.provider != "nim":
            continue
        if not spec.enabled:
            continue
        specs.append({
            "id": spec.id,
            "category": spec.category,
            "capabilities": list(spec.capabilities),
            "context": spec.context,
            "latency": spec.latency,
            "supports_tools": spec.supports_tools,
            "supports_streaming": spec.supports_streaming,
            "supports_structured_output": spec.supports_structured_output,
            "vision": spec.vision,
            "enabled": spec.enabled,
            "health": spec.health.value if spec.health else "enabled",
            "benchmark_score": spec.benchmark_score,
            "priority": spec.priority,
            "fallbacks": list(spec.fallbacks),
            "available": spec.id in available,
        })
    return {"models": sorted(specs, key=lambda m: m["benchmark_score"], reverse=True)}


@router.get("/route")
def nim_route(
    query: str = "",
    content_type: str = "",
    complexity: str = "simple",
    mode: str = "auto",
):
    """
    Route a request to the best NIM model.

    Args:
        query: The user's query string
        content_type: 'image', 'video', 'audio', 'code', etc.
        complexity: 'simple', 'complex', 'interactive'
        mode: 'auto', 'fast', 'think', 'coding', 'vision', 'translation', 'safety'
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    router = BenchmarkRouter()
    cap = router.capability_for(query, content_type=content_type, complexity=complexity)

    candidates = model_registry.by_capability(cap, enabled_only=True)

    if not candidates:
        candidates = model_registry.by_capability("reasoning", enabled_only=True)

    if not candidates:
        raise HTTPException(status_code=404, detail="No NIM models found for capability")

    scores = [(m, m.benchmark_score) for m in candidates]
    scores.sort(key=lambda x: x[1], reverse=True)

    selected = scores[0][0]

    chain = []
    for model_id in selected.fallbacks[:3]:
        m = model_registry.get(model_id)
        if m and m.enabled:
            chain.append(m)

    return {
        "capability": cap,
        "selected": selected.id,
        "model": {
            "id": selected.id,
            "category": selected.category,
            "latency": selected.latency,
            "benchmark_score": selected.benchmark_score,
            "supports_tools": selected.supports_tools,
        },
        "fallback_chain": [m.id for m in chain],
        "reason": f"{cap} task (score: {selected.benchmark_score})",
    }


@router.post("/chat")
async def nim_chat(request: Request, body: dict):
    """
    Non-streaming chat through NIM with automatic model selection.

    Uses benchmark-aware routing for optimal model choice.
    """
    provider = _require_provider(request)
    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")

    router = BenchmarkRouter()
    cap = router.capability_for(str(messages))

    candidates = model_registry.by_capability(cap, enabled_only=True)

    if not candidates:
        raise HTTPException(status_code=404, detail=f"No NIM models for capability: {cap}")

    for model in candidates:
        try:
            data = await provider.chat(model.id, messages)
            content = data["choices"][0]["message"].get("content") or ""
            return {
                "content": content,
                "model": model.id,
                "capability": cap,
                "benchmark_score": model.benchmark_score,
                "finish_reason": data["choices"][0].get("finish_reason"),
                "usage": data.get("usage"),
            }
        except Exception as e:
            log.warning("NIM model %s failed: %s", model.id, e)
            continue

    raise HTTPException(status_code=502, detail="All NIM models failed")


@router.post("/stream")
async def nim_stream(request: Request, body: dict):
    """Stream text from NIM through the provider."""
    provider = _require_provider(request)
    messages = body.get("messages")
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")

    router = BenchmarkRouter()
    cap = router.capability_for(str(messages))

    model = model_registry.get_recommended_model(cap)
    if model is None:
        raise HTTPException(status_code=404, detail="No suitable NIM model found")

    if not model.enabled or model.health != model_registry.ModelHealth.AVAILABLE:
        raise HTTPException(status_code=404, detail=f"Model {model.id} is not healthy")

    async def gen():
        try:
            async for token in provider.chat_stream(model.id, messages):
                yield f"data: {token}\n\n"
        except Exception as e:
            log.error("NIM streaming failed: %s", e)
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")