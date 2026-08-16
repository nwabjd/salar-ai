# backend/app/services/world_model/evolution.py
"""EvolutionEngine — learns action policies from execution outcomes.

Self-evolution loop:
  1. The agent/planner proposes actions for situations.
  2. Each executed action is recorded as a WorldActionExecution (outcome,
     whether the situation resolved afterward).
  3. evolve() aggregates executions into WorldActionPolicy rows with a
     bounded success score.
  4. SituationActionPlanner ranks proposed actions by learned score, so
     actions that historically resolve situations get proposed first.

This is the first, deterministic step toward self-evolving behavior:
policies only improve with real evidence from actual executions.
"""

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .actions import ActionPlan

log = logging.getLogger(__name__)

# How long a resolution event stays relevant to a preceding execution.
_RESOLUTION_WINDOW_DAYS = 2
# Bayesian prior so a single trial doesn't max out a score.
_PRIOR_SUCCESS = 1.0
_PRIOR_TOTAL = 3.0
# Gamma-correction so high-attempt, high-success actions outrank early wins.
_SCORE_GAMMA = 0.4


class EvolutionEngine:
    def __init__(self, db) -> None:
        self.db = db

    # ---------------- recording ----------------

    def record_execution(
        self,
        user_id: str,
        situation_kind: str,
        action_title: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        *,
        outcome: str = "unknown",
        resolved: bool = False,
        detail: str = "",
    ) -> str:
        """Persist one executed action for later policy learning."""
        from ...models import WorldActionExecution

        if situation_kind not in ("failing_build", "deadline_pressure", "collaborator_activity",
                                  "direct_message", "resource_pressure", "task_due", "active_context"):
            situation_kind = "unknown"
        if outcome not in ("success", "failure", "neutral", "unknown"):
            outcome = "unknown"

        row = WorldActionExecution(
            user_id=user_id,
            situation_kind=situation_kind,
            action_title=action_title,
            tool_calls_json=json.dumps(tool_calls or [], default=str),
            outcome=outcome,
            resolved=resolved,
            detail=detail,
        )
        self.db.add(row)
        self.db.flush()
        return row.id

    def record_resolution(self, user_id: str, situation_kind: str, *, resolved: bool = True) -> None:
        """Mark recent executions of this situation as having resolved it.

        Called when the world model observes that a situation went away —
        giving the actions executed shortly before the credit.
        """
        from ...models import WorldActionExecution

        cutoff = self._utcnow() - timedelta(days=_RESOLUTION_WINDOW_DAYS)
        rows = list(self.db.scalars(
            select(WorldActionExecution).where(
                WorldActionExecution.user_id == user_id,
                WorldActionExecution.situation_kind == situation_kind,
                WorldActionExecution.created_at >= cutoff,
                WorldActionExecution.resolved.is_(False),
            ).order_by(WorldActionExecution.created_at.desc()).limit(5)
        ))
        for row in rows:
            row.resolved = True

    # ---------------- learning ----------------

    def evolve(self, user_id: str) -> List[Dict[str, Any]]:
        """Aggregate executions into updated policies for this user."""
        from ...models import WorldActionExecution, WorldActionPolicy

        executions = list(self.db.scalars(
            select(WorldActionExecution).where(
                WorldActionExecution.user_id == user_id,
            ).order_by(WorldActionExecution.created_at.asc())
        ))

        aggregates: Dict[tuple, Dict[str, Any]] = {}
        for ex in executions:
            key = (ex.situation_kind, ex.action_title or "(unnamed)")
            agg = aggregates.setdefault(key, {"attempts": 0, "successes": 0, "resolved": 0})
            agg["attempts"] += 1
            if ex.outcome == "success":
                agg["successes"] += 1
            if ex.resolved:
                agg["resolved"] += 1

        updated = []
        for (kind, title), agg in aggregates.items():
            score = self._compute_score(agg["attempts"], agg["successes"], agg["resolved"])
            policy = self.db.scalar(
                select(WorldActionPolicy).where(
                    WorldActionPolicy.user_id == user_id,
                    WorldActionPolicy.situation_kind == kind,
                    WorldActionPolicy.action_title == title,
                )
            )
            if policy is None:
                from ...models import WorldActionPolicy as Policy
                policy = Policy(user_id=user_id, situation_kind=kind, action_title=title)
                self.db.add(policy)
            policy.attempts = agg["attempts"]
            policy.successes = agg["successes"]
            policy.resolved_count = agg["resolved"]
            policy.score = score
            policy.last_seen = self._utcnow()
            updated.append({
                "situation_kind": kind,
                "action_title": title,
                "attempts": policy.attempts,
                "successes": policy.successes,
                "resolved_count": policy.resolved_count,
                "score": round(policy.score, 3),
            })

        self.db.flush()
        return sorted(updated, key=lambda p: p["score"], reverse=True)

    def policies(self, user_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        from ...models import WorldActionPolicy

        rows = list(self.db.scalars(
            select(WorldActionPolicy).where(WorldActionPolicy.user_id == user_id)
            .order_by(WorldActionPolicy.score.desc(), WorldActionPolicy.attempts.desc())
            .limit(limit)
        ))
        return [{
            "situation_kind": r.situation_kind,
            "action_title": r.action_title,
            "attempts": r.attempts,
            "successes": r.successes,
            "resolved_count": r.resolved_count,
            "score": round(r.score, 3),
        } for r in rows]

    def score_for(self, user_id: str, situation_kind: str, action_title: str) -> float:
        """Return the learned score for an (action, situation) pair (0 default)."""
        from ...models import WorldActionPolicy

        policy = self.db.scalar(
            select(WorldActionPolicy).where(
                WorldActionPolicy.user_id == user_id,
                WorldActionPolicy.situation_kind == situation_kind,
                WorldActionPolicy.action_title == action_title,
            )
        )
        return policy.score if policy is not None else 0.0

    # ---------------- scoring ----------------

    @staticmethod
    def _compute_score(attempts: int, successes: int, resolved: int) -> float:
        """Bounded 0..1 score from attempts/successes/resolutions.

        Uses a Bayesian prior so low-evidence actions don't jump to extremes,
        then gamma-corrects so sustained wins beat single flukes.
        """
        total = _PRIOR_TOTAL + attempts
        success_est = (_PRIOR_SUCCESS + successes + resolved) / total
        evidence = attempts / _PRIOR_TOTAL
        return max(0.0, min(1.0, success_est * (evidence ** _SCORE_GAMMA)))

    @staticmethod
    def _utcnow():
        from ...models import utcnow
        return utcnow()
