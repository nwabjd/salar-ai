"""
Model Router — Enhanced with benchmark-aware routing for SALAAR's intelligence backbone.

COMPATIBILITY: This module maintains backward compatibility with the existing
Gemini-only routing for /api/models and tests. The new BenchmarkRouter (NIMRouter)
uses the model_registry for capability-aware routing based on real benchmark scores.

USAGE:
- Fast Gemini routing: ModelRouter() (existing behavior for compatibility)
- Benchmark-aware NIM routing: BenchmarkRouter() (uses model_registry, scores)
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Optional

from .model_registry import (
    ModelSpec,
    ModelHealth,
    MODELS,
    by_capability,
    get as get_model,
)

# Legacy registry for backward compatibility with existing tests
MODEL_REGISTRY = {
    "light": ["gemini-3.1-flash-lite"],
    "chat": ["gemini-3.1-flash-lite"],
    "code": ["gemini-3.1-flash-lite"],
    "vision": ["gemini-3.1-pro-vision"],
    "reasoning": ["gemini-3.1-pro"],
    "research": ["gemini-3.1-pro"],
    "creative": ["gemini-3.1-pro"],
    "voice": ["gemini-3.1-flash-live-preview"],
}

_CODE_RE = re.compile(
    r"def |function |class |import |npm |git |compile |debug |python|javascript|typescript|react|build|error|traceback|stack trace|代码|编码|程式"
)
_VISION_RE = re.compile(r"screenshot|image|图片|截图")
_RESEARCH_RE = re.compile(r"research|compare sources|deep research|investigate|verify")
_REASONING_RE = re.compile(r"explain deeply|analyze|compare and contrast|weigh pros and cons|decision")
_CREATIVE_RE = re.compile(r"creative|image generation|ad concept|brainstorm")

_CODE_TOOLS = {"run_command", "code_run"}
_VISION_TOOLS = {"screenshot", "camera"}


class ModelRouterError(Exception):
    pass


class ModelRouter:
    """
    Legacy Gemini-only router for backward compatibility.
    
    Used by existing /api/models endpoints and tests.
    """
    def __init__(self, settings=None):
        self._registry = deepcopy(MODEL_REGISTRY)
        if settings is not None:
            if getattr(settings, "gemini_model", None):
                for cap in ("light", "chat", "code"):
                    self._registry[cap] = [settings.gemini_model]
            if getattr(settings, "gemini_live_model", None):
                self._registry["voice"] = [settings.gemini_live_model]

    def capabilities(self):
        return deepcopy(self._registry)

    def capability_for(self, query: str, *, content_type: str = "", complexity: str = "simple"):
        q = (query or "").lower()
        ct = (content_type or "").lower()
        if ct in ("image", "screenshot", "vision"):
            return "vision"
        if ct in ("voice", "audio"):
            return "voice"
        if ct in ("image_generation", "creative"):
            return "creative"
        if ct == "code" or _CODE_RE.search(q):
            return "code"
        if _VISION_RE.search(q):
            return "vision"
        if _RESEARCH_RE.search(q):
            return "research"
        if complexity == "complex" or _REASONING_RE.search(q):
            return "reasoning"
        if _CREATIVE_RE.search(q):
            return "creative"
        return "light"

    def route(self, query: str, *, content_type: str = "", complexity: str = "simple"):
        cap = self.capability_for(query, content_type=content_type, complexity=complexity)
        return self.model_for(cap)

    def route_for_tools(self, tool_names, query: str = ""):
        tools = {str(t).lower() for t in (tool_names or [])}
        if tools & _CODE_TOOLS:
            return self.model_for("code")
        if tools & _VISION_TOOLS:
            return self.model_for("vision")
        return self.route(query)

    def model_for(self, capability: str):
        models = self._registry.get(capability)
        if not models:
            raise ModelRouterError(f"No models registered for capability: {capability}")
        return models[0]


# ============================================================================
# Benchmark Router — Uses real model registry with scores for NIM routing
# ============================================================================

AVG_LATENCY_SECONDS = {
    "fast": 1.0,
    "medium": 5.0,
    "slow": 30.0,
}


def _score_model(model: ModelSpec, complexity: str = "simple") -> float:
    """
    Calculate routing score for a model based on benchmark data.
    
    Score = (benchmark * 0.4) + (health * 0.25) + (latency_penalty * 0.20) + (instruction * 0.15)
    Higher score = better choice.
    """
    health_factor = 1.0 if model.health == ModelHealth.AVAILABLE else 0.0
    if not model.enabled:
        health_factor = 0.0
    
    # Latency penalty: faster is better
    base_latency = AVG_LATENCY_SECONDS.get(model.latency, 5.0)
    latency_penalty = max(0, 1.0 - (base_latency / 60.0))  # Normalize against 60s max
    
    # Instruction following quality (from benchmark)
    inst_factor = model.benchmark_score
    
    score = (
        model.benchmark_score * 0.40 +
        health_factor * 0.25 +
        latency_penalty * 0.20 +
        inst_factor * 0.15
    )
    
    # Bonus for task match: if capability matches complexity
    if complexity == "complex" and "reasoning" in model.capabilities:
        score += 0.1
    if complexity == "simple" and "fast" in model.capabilities:
        score += 0.05
    
    return round(score, 3)


class BenchmarkRouter:
    """
    Benchmark-aware router using the model_registry for dynamic model selection.
    
    Uses real measured scores, latency, and health status to pick the best model.
    """
    def __init__(self, default_provider: Optional[str] = None):
        self.default_provider = default_provider

    def capability_for(self, query: str, *, content_type: str = "", complexity: str = "simple"):
        q = (query or "").lower()
        ct = (content_type or "").lower()
        if ct in ("image", "screenshot", "vision"):
            return "multimodal"
        if ct in ("voice", "audio"):
            return "multimodal"
        if ct in ("image_generation", "creative"):
            return "creative"
        if ct == "code":
            return "coding"
        if _VISION_RE.search(q):
            return "multimodal"
        if _RESEARCH_RE.search(q):
            return "reasoning"
        if complexity == "complex" or _REASONING_RE.search(q):
            return "reasoning"
        if _CREATIVE_RE.search(q):
            return "creative"
        return "coding"  # Default to coding (Laguna handles general chat well)

    def route(self, query: str, *, content_type: str = "", complexity: str = "simple"):
        cap = self.capability_for(query, content_type=content_type, complexity=complexity)
        return self.model_for(cap)

    def model_for(self, capability: str) -> Optional[ModelSpec]:
        """Get best model for capability using benchmark scores."""
        # Try by capability first
        candidates = by_capability(capability, enabled_only=True)
        if not candidates:
            # Fall back to models that can handle this capability
            candidates = by_capability("reasoning", enabled_only=True)
        
        if not candidates:
            return None

        # Sort by score
        scored = [(m, _score_model(m)) for m in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return top available
        for model, score in scored:
            if model.enabled and model.health == ModelHealth.AVAILABLE:
                return model
        
        return scored[0][0] if scored else None

    def chain(self, start_id: str, limit: int = 4):
        """Get fallback chain for a model."""
        from .model_registry import chain as _chain
        return _chain(start_id, limit)


def get(model_id: str):
    """Get model by ID."""
    return get_model(model_id)


__all__ = [
    "ModelRouter",
    "ModelRouterError",
    "BenchmarkRouter",
    "_score_model",
    "get",
]