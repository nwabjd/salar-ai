# backend/app/services/missions/planner.py
import json
import logging
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)

_MAX_PLAN_ATTEMPTS = 3
_MAX_STEPS = 50


class PlanningError(Exception):
    pass


class MissionPlanner:
    def __init__(self, gemini, *, known_tools: Optional[Set[str]] = None) -> None:
        self._gemini = gemini
        self._known_tools = known_tools

    async def plan(self, goal: str) -> List[Dict[str, Any]]:
        prompt = self._build_plan_prompt(goal)
        return await self._call(prompt)

    async def replan(
        self,
        goal: str,
        completed_steps: List[Dict[str, Any]],
        failed_step: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        progress = {
            "completed": completed_steps,
            "failed": failed_step,
        }
        prompt = self._replan_prompt(goal, progress)
        return await self._call(prompt)

    async def _call(self, prompt: str) -> List[Dict[str, Any]]:
        messages = [
            {"role": "user", "content": prompt},
        ]
        last_error = None
        for _ in range(_MAX_PLAN_ATTEMPTS):
            try:
                text = await self._gemini.chat(messages)
                data = json.loads(text)
                steps = data.get("steps", [])
                if not isinstance(steps, list) or len(steps) == 0:
                    last_error = "empty steps"
                    continue
                if len(steps) > _MAX_STEPS:
                    last_error = f"too many steps ({len(steps)})"
                    continue
                for i, step in enumerate(steps):
                    tool = step.get("tool")
                    if not tool or not isinstance(tool, str):
                        last_error = f"step {i} missing tool"
                        break
                    if self._known_tools and tool not in self._known_tools:
                        last_error = f"step {i} unknown tool '{tool}'"
                        break
                    if not isinstance(step.get("args"), dict):
                        last_error = f"step {i} args not a dict"
                        break
                else:
                    return steps
            except json.JSONDecodeError as exc:
                last_error = str(exc)
            except Exception as exc:
                last_error = str(exc)
            log.warning("Planner attempt failed: %s", last_error)
        raise PlanningError(f"Planning failed after {_MAX_PLAN_ATTEMPTS} attempts: {last_error}")

    @staticmethod
    def _build_plan_prompt(goal: str) -> str:
        return (
            "You are SALAR's mission planner. Turn the user's goal into an ordered plan.\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON with a \"steps\" array.\n"
            "- Each step: {\"tool\": str, \"args\": {}, \"rationale\": str}.\n"
            "- Only use tools that exist in the system; never invent tools.\n"
            "- One tool call per step.\n"
            "- Max 50 steps.\n"
            "- Put steps in logical execution order.\n\n"
            "Output format: {\"steps\": [{\"tool\": \"...\", \"args\": {...}, \"rationale\": \"...\"}, ...]}\n\n"
            f"Goal: {goal}"
        )

    @staticmethod
    def _replan_prompt(goal: str, progress: dict) -> str:
        return (
            "You are SALAR's mission planner re-planning after a partial failure.\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON with a \"steps\" array for the REMAINING work.\n"
            "- Do not repeat steps already completed successfully.\n"
            "- Each step: {\"tool\": str, \"args\": {}, \"rationale\": str}.\n"
            "- One tool call per step, max 50 steps.\n"
            "- Only use tools that exist in the system.\n\n"
            f"Original goal: {goal}\n\n"
            f"Progress so far: {json.dumps(progress)}\n\n"
            "Remaining plan:"
        )
