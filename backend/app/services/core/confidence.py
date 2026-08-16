# backend/app/services/core/confidence.py
import logging
import math
from typing import Dict, Optional

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.7


class ConfidenceSystem:
    def __init__(self) -> None:
        self.default_threshold = DEFAULT_THRESHOLD

    @staticmethod
    def combine(factors: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> float:
        """Weighted geometric mean of confidence factors (all clamped 0..1)."""
        if not factors:
            return 0.0
        clamped = {k: min(max(float(v), 0.0), 1.0) for k, v in factors.items()}
        if any(v <= 0.0 for v in clamped.values()):
            return 0.0
        weights = weights or {k: 1.0 for k in clamped}
        total = sum(max(float(weights.get(k, 1.0)), 0.0) for k in clamped)
        if total <= 0:
            return 0.0
        log_sum = sum(float(weights.get(k, 1.0)) * math.log(max(v, 1e-9)) for k, v in clamped.items())
        return math.exp(log_sum / total)

    @staticmethod
    def escalate(score: float, threshold: Optional[float] = None) -> bool:
        """True when the score is below threshold (decision needs escalation)."""
        if threshold is None:
            threshold = DEFAULT_THRESHOLD
        return score < threshold
