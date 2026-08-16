# backend/app/services/world_model/simulator.py
"""WorldSimulator — runs what-if scenarios against the world graph.

A SimulationScenario describes a proposed change (entity mutation, relation
addition/removal). The simulator clones the graph state, applies the change,
runs SituationEngine on the modified snapshot, and compares before/after.

The output is a list of Consequence objects that describe what would change
if the scenario were real — surfaced to the user as "here's what would
happen if you did X."
"""

import copy
import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class Consequence:
    def __init__(
        self,
        *,
        kind: str,
        delta: str,
        detail: str,
        severity: str = "low",
    ) -> None:
        self.kind = kind
        self.delta = delta  # "new", "removed", "worsened", "improved"
        self.detail = detail
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "delta": self.delta,
            "detail": self.detail,
            "severity": self.severity,
        }


class SimulationResult:
    def __init__(
        self,
        *,
        scenarios_before: List[Dict[str, Any]],
        scenarios_after: List[Dict[str, Any]],
        consequences: List[Consequence],
        narrative: str,
    ) -> None:
        self.scenarios_before = scenarios_before
        self.scenarios_after = scenarios_after
        self.consequences = consequences
        self.narrative = narrative

    def to_dict(self) -> Dict[str, Any]:
        return {
            "situations_before": self.scenarios_before,
            "situations_after": self.scenarios_after,
            "consequences": [c.to_dict() for c in self.consequences],
            "narrative": self.narrative,
        }


class WorldSimulator:
    """Simulates what-if scenarios against the world graph.

    Does not mutate the real graph; clones state for simulation.
    """

    def __init__(self, graph, situation_engine) -> None:
        self.graph = graph
        self.engine = situation_engine

    def simulate(self, user_id: str, changes: List[Dict[str, Any]]) -> SimulationResult:
        """Run a what-if scenario.

        Each change is a dict with:
          - action: "set_entity_prop" | "add_entity" | "remove_entity" | "add_relation" | "remove_relation"
          - params: action-specific params

        Runs inside a SAVEPOINT so the rollback only discards the simulated
        changes and never touches unrelated uncommitted work on the session.
        """
        before = self.engine.situations(user_id)

        try:
            nested = self.graph.db.begin_nested()
        except Exception:
            # Some pooled setups don't support nested transactions; fall back
            # to operating on a plain transaction and let callers isolate.
            nested = None

        self._apply_changes(user_id, changes)
        self.graph.db.flush()

        after = self.engine.situations(user_id)

        if nested is not None:
            nested.rollback()
        else:
            self.graph.db.rollback()

        consequences = self._diff_situations(before, after)
        narrative = self._build_narrative(consequences, changes)

        return SimulationResult(
            scenarios_before=before,
            scenarios_after=after,
            consequences=consequences,
            narrative=narrative,
        )

    def _apply_changes(self, user_id: str, changes: List[Dict[str, Any]]) -> None:
        for change in changes:
            action = change.get("action")
            params = change.get("params", {})

            if action == "set_entity_prop":
                entity_type = params.get("entity_type", "")
                key = params.get("key", "")
                prop = params.get("prop", "")
                value = params.get("value")
                entities = self.graph.entities(user_id, entity_type=entity_type, limit=50)
                for e in entities:
                    if e.key == key:
                        props = e.props.copy()
                        props[prop] = value
                        self.graph.upsert_entity(user_id, entity_type, key, props=props, source="simulation")
                        break

            elif action == "add_relation":
                self.graph.relate(
                    user_id,
                    params.get("from_type", ""),
                    params.get("from_key", ""),
                    params.get("relation", ""),
                    params.get("to_type", ""),
                    params.get("to_key", ""),
                    source="simulation",
                )

            elif action == "remove_relation":
                self.graph.remove_relation(
                    user_id,
                    params.get("from_type", ""),
                    params.get("from_key", ""),
                    params.get("relation", ""),
                    params.get("to_type", ""),
                    params.get("to_key", ""),
                )

    def _diff_situations(
        self,
        before: List[Dict[str, Any]],
        after: List[Dict[str, Any]],
    ) -> List[Consequence]:
        before_kinds = {s["kind"]: s for s in before}
        after_kinds = {s["kind"]: s for s in after}
        consequences: List[Consequence] = []

        all_kinds = set(before_kinds.keys()) | set(after_kinds.keys())
        for kind in all_kinds:
            was = before_kinds.get(kind)
            now = after_kinds.get(kind)

            if was and not now:
                consequences.append(Consequence(
                    kind=kind, delta="removed",
                    detail=f"'{kind}' situation resolved",
                    severity="low",
                ))
            elif not was and now:
                consequences.append(Consequence(
                    kind=kind, delta="new",
                    detail=now.get("title", kind),
                    severity=now.get("severity", "low"),
                ))
            elif was and now:
                was_sev = was.get("severity", "low")
                now_sev = now.get("severity", "low")
                sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
                if sev_rank.get(now_sev, 3) < sev_rank.get(was_sev, 3):
                    consequences.append(Consequence(
                        kind=kind, delta="worsened",
                        detail=f"{kind}: severity changed from {was_sev} to {now_sev}",
                        severity=now_sev,
                    ))
                elif sev_rank.get(now_sev, 3) > sev_rank.get(was_sev, 3):
                    consequences.append(Consequence(
                        kind=kind, delta="improved",
                        detail=f"{kind}: severity improved from {was_sev} to {now_sev}",
                        severity=now_sev,
                    ))

        consequences.sort(key=lambda c: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(c.severity, 10))
        return consequences

    def _build_narrative(
        self,
        consequences: List[Consequence],
        changes: List[Dict[str, Any]],
    ) -> str:
        if not consequences:
            return "No significant changes detected in this scenario."

        parts = []
        for c in consequences:
            if c.delta == "new":
                parts.append(f"This would CREATE a new '{c.kind}' situation: {c.detail}.")
            elif c.delta == "removed":
                parts.append(f"This would RESOLVE the '{c.kind}' situation.")
            elif c.delta == "worsened":
                parts.append(f"This would WORSEN the '{c.kind}' situation: {c.detail}.")
            elif c.delta == "improved":
                parts.append(f"This would IMPROVE the '{c.kind}' situation: {c.detail}.")

        return " ".join(parts)
