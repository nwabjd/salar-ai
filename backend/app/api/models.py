"""Intelligent model router endpoints — inspect models and route a request to the best model."""

from fastapi import APIRouter, HTTPException, Request

from ..services.model_router import ModelRouter

router = APIRouter(prefix="/api/models", tags=["models"])

_REASONS = {
    "light": "simple text request",
    "chat": "general chat request",
    "code": "code-related request",
    "vision": "visual content request",
    "voice": "voice/audio request",
    "creative": "creative or image generation request",
    "research": "deep research request",
    "reasoning": "complex reasoning request",
}


def _router(request: Request) -> ModelRouter:
    settings = getattr(request.app.state, "settings", None)
    return ModelRouter(settings)


@router.get("")
def list_models(request: Request):
    registry = _router(request).capabilities()
    flat = {}
    for cap, models in registry.items():
        for name in models:
            flat.setdefault(name, set()).add(cap)
    models = [
        {"name": name, "capabilities": sorted(caps)}
        for name, caps in sorted(flat.items())
    ]
    settings = getattr(request.app.state, "settings", None)
    default = getattr(settings, "gemini_model", "gemini-3.1-flash-lite")
    return {"models": models, "default": default}


@router.get("/route")
def route_model(request: Request, query: str = "", content_type: str = "", complexity: str = "simple"):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    router = _router(request)
    cap = router.capability_for(query, content_type=content_type, complexity=complexity)
    return {
        "model": router.model_for(cap),
        "capability": cap,
        "reason": _REASONS.get(cap, "routed request"),
    }
