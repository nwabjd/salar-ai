"""
Health tracking and fallback management for SALAR's intelligence backbone.

Tracks model availability, latency, and success rates to enable
health-aware routing decisions.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .model_registry import ModelSpec, ModelHealth


@dataclass
class ModelMetrics:
    """Performance metrics for a model."""
    requests: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    rate_limited_count: int = 0
    timeout_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.requests == 0:
            return 1.0
        return self.successes / self.requests

    @property
    def avg_latency_ms(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.total_latency_ms / self.requests


class HealthTracker:
    """
    Tracks health metrics for models and adjusts routing decisions.

    Maintains metrics for each provider/model and provides
    health-aware model recommendations.
    """

    def __init__(self, window_seconds: int = 3600):
        self._metrics: Dict[str, ModelMetrics] = defaultdict(ModelMetrics)
        self._window_seconds = window_seconds

    def record_success(self, model_id: str, latency_ms: float = 0.0):
        """Record a successful request."""
        m = self._metrics[model_id]
        m.requests += 1
        m.successes += 1
        m.total_latency_ms += latency_ms
        m.last_success = time.time()

    def record_failure(self, model_id: str, error_type: str = "error"):
        """Record a failed request."""
        m = self._metrics[model_id]
        m.requests += 1
        m.failures += 1
        m.last_failure = time.time()
        if error_type == "rate_limit":
            m.rate_limited_count += 1
        elif error_type == "timeout":
            m.timeout_count += 1

    def record_request(self, model_id: str, latency_ms: float, success: bool):
        """Record a complete request cycle."""
        if success:
            self.record_success(model_id, latency_ms)
        else:
            self.record_failure(model_id)

    def get_metrics(self, model_id: str) -> ModelMetrics:
        self._clean_old_metrics()
        return self._metrics.get(model_id, ModelMetrics())

    def get_health_status(self, model: ModelSpec) -> ModelHealth:
        """Determine health status based on recent metrics."""
        metrics = self.get_metrics(model.id)

        if not model.enabled:
            return ModelHealth.DISABLED

        if metrics.requests == 0:
            return ModelHealth.AVAILABLE

        if metrics.success_rate < 0.5:
            return ModelHealth.UNAVAILABLE

        if metrics.rate_limited_count > 10:
            return ModelHealth.RATE_LIMITED

        return ModelHealth.AVAILABLE

    def recommend_fallback(
        self, 
        model: ModelSpec, 
        models: List[ModelSpec]
    ) -> Optional[ModelSpec]:
        """When a model fails, recommend the best healthy fallback."""
        healthy_fallbacks = []
        for m in models:
            if m.id == model.id:
                continue
            health = self.get_health_status(m)
            if health == ModelHealth.AVAILABLE and m.enabled:
                healthy_fallbacks.append((m, m.benchmark_score))

        if not healthy_fallbacks:
            return None

        healthy_fallbacks.sort(key=lambda x: x[1], reverse=True)
        return healthy_fallbacks[0][0]

    def _clean_old_metrics(self):
        """Remove metrics older than the window."""
        cutoff = time.time() - self._window_seconds
        for model_id in list(self._metrics.keys()):
            m = self._metrics[model_id]
            if m.last_failure and m.last_failure < cutoff:
                m.last_failure = None
            if m.last_success and m.last_success < cutoff:
                m.last_success = None

    def reset(self):
        """Reset all metrics."""
        self._metrics.clear()


# Global health tracker instance
_health_tracker: Optional[HealthTracker] = None


def get_health_tracker() -> HealthTracker:
    """Get or create the global health tracker."""
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = HealthTracker()
    return _health_tracker


def reset_health_tracker():
    """Reset the global health tracker (for testing)."""
    global _health_tracker
    _health_tracker = None


__all__ = [
    "ModelMetrics",
    "HealthTracker",
    "get_health_tracker",
    "reset_health_tracker",
]