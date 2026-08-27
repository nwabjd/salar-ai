"""
Centralized model registry — UPDATED with real NIM diagnostic data.

Source of truth for every model: providers, capabilities, benchmark scores,
health status, and routing hints. All model selection goes through 
ModelRouter and this registry.

Benchmark weights: quality .40, reliability .25, latency .20, instruction .15
(Lower score = slower/less reliable)
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ModelHealth(str, Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ModelSpec:
    """One registered model with full metadata for routing."""
    id: str
    provider: str
    category: str
    capabilities: tuple = ()
    context: int = 128_000
    latency: str = "medium"
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_structured_output: bool = False
    vision: bool = False
    enabled: bool = True
    health: ModelHealth = ModelHealth.AVAILABLE
    priority: int = 50
    benchmark_score: float = 0.5  # 0-1, higher = better
    fallbacks: tuple = ()
    tags: tuple = ()


MODELS: Dict[str, ModelSpec] = {m.id: m for m in [
    # =========================================================================
    # PRIMARY NIM MODELS (from benchmark — highest scores)
    # =========================================================================
    
    # Laguna — BEST OVERALL (score 0.96), PRIMARY SALAAR INTELLIGENCE
    ModelSpec(
        id="poolside/laguna-xs-2.1",
        provider="nim",
        category="coding",
        capabilities=("coding", "debug", "refactor", "architecture", "reasoning", "general", "tools"),
        context=131_072,
        latency="medium",
        supports_tools=True,
        supports_structured_output=True,
        priority=100,
        benchmark_score=0.96,
        fallbacks=(),
        tags=("primary", "general", "code", "default"),
    ),
    
    # Nemotron Lightning — FAST (score 0.90)
    ModelSpec(
        id="nvidia/nemotron-3.5-lightning-30b-a3b",
        provider="nim",
        category="fast",
        capabilities=("fast", "classification", "routing", "chat"),
        context=32_768,
        latency="fast",
        supports_tools=True,
        priority=90,
        benchmark_score=0.90,
        fallbacks=(),
        tags=("fast", "light"),
    ),
    
    # Nemotron Omni — MULTIMODAL (score 0.76)
    ModelSpec(
        id="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        provider="nim",
        category="multimodal",
        capabilities=("vision", "multimodal", "ocr", "reasoning", "encoding"),
        context=131_072,
        latency="medium",
        supports_tools=True,
        vision=True,
        priority=85,
        benchmark_score=0.76,
        fallbacks=(),
        tags=("multimodal", "image", "video", "audio"),
    ),
    
    # Nemotron Super — GENERAL REASONING (score 0.65)
    ModelSpec(
        id="nvidia/nemotron-3-super-120b-a12b",
        provider="nim",
        category="reasoning",
        capabilities=("reasoning", "agentic", "verification", "tools", "chat"),
        context=131_072,
        latency="medium",
        supports_tools=True,
        supports_structured_output=True,
        priority=80,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("reasoning", "general"),
    ),
    
    # Nemotron Nano — FAST GENERAL (score 0.65)
    ModelSpec(
        id="nvidia/nemotron-3-nano-30b-a3b",
        provider="nim",
        category="fast",
        capabilities=("fast", "chat", "agentic_light"),
        context=65_536,
        latency="fast",
        priority=70,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("fast", "light"),
    ),
    
    # Models with score ~0.65 (slightly weaker JSON but fast)
    ModelSpec(
        id="meta/muse-glimmer-30b",
        provider="nim",
        category="creative",
        capabilities=("creative", "generation", "multimodal"),
        context=65_536,
        latency="fast",
        priority=65,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("creative", "media"),
    ),
    ModelSpec(
        id="google/diffusiongemma-26b-a4b-it",
        provider="nim",
        category="vision",
        capabilities=("vision", "multimodal", "reasoning"),
        context=131_072,
        latency="fast",
        vision=True,
        priority=65,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("image", "vision"),
    ),
    ModelSpec(
        id="nvidia/riva-translate-4b-instruct-v2",
        provider="nim",
        category="translation",
        capabilities=("translation",),
        context=8_192,
        latency="fast",
        priority=90,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("translate",),
    ),
    ModelSpec(
        id="nvidia/nemotron-3.5-content-safety",
        provider="nim",
        category="safety",
        capabilities=("safety", "classification"),
        context=8_192,
        latency="fast",
        priority=90,
        benchmark_score=0.65,
        fallbacks=(),
        tags=("safety", "moderate"),
    ),
    
    # DeepSeek V4 Pro — DEEP REASONING (score 0.33)
    # 38s latency, 0.25 quality, intended for offline/batch
    ModelSpec(
        id="deepseek-ai/deepseek-v4-pro-0813",
        provider="nim",
        category="reasoning",
        capabilities=("reasoning", "analysis", "coding", "agentic", "long_context"),
        context=131_072,
        latency="slow",
        supports_tools=True,
        priority=30,
        benchmark_score=0.33,
        enabled=False,
        fallbacks=(),
        tags=("deep", "offline"),
    ),
    
    # DeepSeek V4 Flash — GENERAL (score 0.47, very slow)
    ModelSpec(
        id="deepseek-ai/deepseek-v4-flash-0731",
        provider="nim",
        category="chat",
        capabilities=("chat", "fast"),
        context=131_072,
        latency="slow",
        priority=20,
        benchmark_score=0.47,
        enabled=False,
        fallbacks=(),
        tags=("slow", "flash"),
    ),
    
    # Ultra — DEEP ANALYSIS (score 0.55)
    ModelSpec(
        id="nvidia/nemotron-3-ultra-550b-a55b",
        provider="nim",
        category="reasoning",
        capabilities=("reasoning", "deep_analysis", "verification", "agentic"),
        context=262_144,
        latency="slow",
        priority=40,
        benchmark_score=0.55,
        enabled=True,
        fallbacks=(),
        tags=("deep", "verify"),
    ),
    
    # Isin Calibrattion — CALIBRATION (score 0.55)
    ModelSpec(
        id="nvidia/ising-calibration-1.5-31b",
        provider="nim",
        category="calibration",
        capabilities=("calibration", "confidence", "evaluation"),
        context=65_536,
        latency="medium",
        priority=30,
        benchmark_score=0.55,
        enabled=True,
        fallbacks=(),
        tags=("calibrate",),
    ),
    
    # -- Models NOT in inventory or FAILED --
    # These are registered but disabled/blocked
    
    # Embedding models — FAILED/Disabled
    ModelSpec(
        id="nvidia/nemotron-3-embed-1b",
        provider="nim",
        category="embedding",
        capabilities=("embedding", "semantic_search", "memory"),
        context=8_192,
        latency="fast",
        priority=90,
        benchmark_score=0.5,
        enabled=False,
        health=ModelHealth.DISABLED,
        tags=("embed",),
    ),
    
    # Specialized — NOT_PROVISIONED (404 from account)
    ModelSpec(
        id="nvidia/cosmos3-nano",
        provider="nim",
        category="video",
        capabilities=("video", "vision", "physical_reasoning"),
        context=65_536,
        latency="medium",
        vision=True,
        priority=10,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("video", "specialized"),
    ),
    ModelSpec(
        id="nvidia/cosmos3-nano-reasoner",
        provider="nim",
        category="video",
        capabilities=("video", "vision", "physical_reasoning", "reasoning"),
        context=65_536,
        latency="medium",
        vision=True,
        priority=10,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("video", "reasoning"),
    ),
    ModelSpec(
        id="nvidia/cosm-transfer2.5-2b",
        provider="nim",
        category="specialized",
        capabilities=("media_transform", "vision"),
        latency="medium",
        priority=10,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("media",),
    ),
    ModelSpec(
        id="nvidia/synthetic-video-detector",
        provider="nim",
        category="specialized",
        capabilities=("video_analysis", "authenticity"),
        latency="medium",
        priority=10,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("video", "authenticity"),
    ),
    ModelSpec(
        id="nvidia/active-speaker-detection",
        provider="nim",
        category="specialized",
        capabilities=("audio_analysis", "speaker_detection"),
        latency="medium",
        priority=10,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("audio", "speaker"),
    ),
    ModelSpec(
        id="nvidia/ising-calibration-1-35b-a3b",
        provider="nim",
        category="calibration",
        capabilities=("calibration", "confidence", "evaluation"),
        context=65_536,
        latency="medium",
        priority=30,
        enabled=False,
        health=ModelHealth.UNAVAILABLE,
        tags=("calibrate",),
    ),
    
    # -- Existing providers (unchanged) --
    ModelSpec(
        id="gemini-3.1-flash-lite",
        provider="gemini",
        category="chat",
        capabilities=("chat", "tools"),
        supports_tools=True,
        context=1_000_000,
        latency="fast",
        priority=85,
        fallbacks=("gemini-3.1-pro",),
        tags=("cloud", "default"),
    ),
    ModelSpec(
        id="gemini-3.1-pro",
        provider="gemini",
        category="reasoning",
        capabilities=("reasoning", "tools", "vision"),
        supports_tools=True,
        vision=True,
        context=1_000_000,
        latency="medium",
        priority=90,
        tags=("cloud",),
    ),
    ModelSpec(
        id="salar-tuned",
        provider="ollama",
        category="chat",
        capabilities=("chat", "tools"),
        supports_tools=True,
        context=65_536,
        latency="fast",
        priority=70,
        tags=("local",),
    ),
]}


def get(model_id: str) -> Optional[ModelSpec]:
    return MODELS.get(model_id)


def by_category(
    category: str,
    provider: Optional[str] = None,
    enabled_only: bool = True,
    health: Optional[ModelHealth] = None,
) -> List[ModelSpec]:
    """Get models by category, optionally filtered by provider, enabled status, and health."""
    out = []
    for m in MODELS.values():
        if m.category != category:
            continue
        if provider is not None and m.provider != provider:
            continue
        if enabled_only and not m.enabled:
            continue
        if health is not None and m.health != health:
            continue
        out.append(m)
    out.sort(key=lambda m: m.benchmark_score * 100 + m.priority, reverse=True)
    return out


def by_capability(capability: str, enabled_only: bool = True) -> List[ModelSpec]:
    """Get models that support a given capability."""
    out = [m for m in MODELS.values() if capability in m.capabilities]
    if enabled_only:
        out = [m for m in out if m.enabled]
    out.sort(key=lambda m: m.benchmark_score * 100 + m.priority, reverse=True)
    return out


def chain(start_id: str, limit: int = 4) -> List[ModelSpec]:
    """Resolve the ordered fallback chain starting at start_id."""
    seen, order = set(), []
    cur = get(start_id)
    while cur and cur.id not in seen and len(order) < limit:
        order.append(cur)
        seen.add(cur.id)
        nxt = get(cur.fallbacks[0]) if cur.fallbacks else None
        cur = nxt
    return order


def get_recommended_model(capability: str, content_type: str = "") -> ModelSpec:
    """Get the recommended model for a capability, respecting health and benchmarks."""
    models = by_capability(capability, enabled_only=True)
    for m in models:
        if m.health == ModelHealth.AVAILABLE and m.enabled:
            return m
    return models[0] if models else None


__all__ = [
    "ModelSpec", "ModelHealth", "MODELS", "get", "by_category", 
    "by_capability", "chain", "get_recommended_model",
]