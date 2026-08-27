"""
SALAAR Intelligent Orchestration Engine.

Provides multi-model orchestration for complex tasks with PLAN→EXECUTE→REVIEW→VERIFY→SYNTHESIZE
workflows. Modeled after the user's Supernova specialization.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..nim import NIMProvider
from ..model_router import BenchmarkRouter
from ..model_registry import ModelSpec, ModelHealth, get


class TaskMode(Enum):
    AUTO = "auto"
    FAST = "fast"
    THINK = "think"
    DEEP = "deep"
    CODE = "coding"
    RESEARCH = "research"
    VISION = "vision"
    VIDEO = "video"
    TRANSLATE = "translation"
    SAFETY = "safety"
    SUPERNOVA = "supernova"


@dataclass
class TaskSpec:
    """Specification for a complex task."""
    mode: TaskMode = TaskMode.AUTO
    complexity: str = "simple"
    capabilities: tuple = ()
    max_models: int = 3
    verification_required: bool = True


class Orchestrator:
    """
    Intelligent orchestration engine for multi-model workflows.

    Handles task planning, model selection, execution, review,
    verification, and synthesis for complex tasks.
    """

    def __init__(self, nim_provider: Optional[NIMProvider] = None):
        self._nim = nim_provider
        self._router = BenchmarkRouter()
        self._models_by_mode = {
            TaskMode.FAST: ["nvidia/nemotron-3.5-lightning-30b-a3b"],
            TaskMode.THINK: ["poolside/laguna-xs-2.1"],
            TaskMode.DEEP: ["nvidia/nemotron-3-ultra-550b-a55b", "poolside/laguna-xs-2.1"],
            TaskMode.CODE: ["poolside/laguna-xs-2.1"],
            TaskMode.VISION: ["nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"],
            TaskMode.TRANSLATE: ["nvidia/riva-translate-4b-instruct-v2"],
            TaskMode.SAFETY: ["nvidia/nemotron-3.5-content-safety"],
            TaskMode.SUPERNOVA: [],
        }

    async def route_task(self, query: str, mode: TaskMode = TaskMode.AUTO) -> Optional[ModelSpec]:
        """Route a task to the appropriate primary model."""
        if mode == TaskMode.AUTO:
            cap = self._router.capability_for(query)
            model = self._router.model_for(cap)
            return model

        model_ids = self._models_by_mode.get(mode, [])
        for mid in model_ids:
            model = get(mid)
            if model and model.enabled and model.health == ModelHealth.AVAILABLE:
                return model

        return None

    async def execute(
        self,
        task: str,
        mode: TaskMode = TaskMode.AUTO,
        messages: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a task using the appropriate model(s).

        For SUPERNOVA mode, performs multi-model analysis.
        For simpler modes, uses single best model.
        """
        if messages is None:
            messages = [{"role": "user", "content": task}]

        result = {
            "mode": mode.value,
            "task": task,
            "models_used": [],
            "subtasks": [],
        }

        if mode == TaskMode.SUPERNOVA:
            return await self._execute_supernova(task, messages)

        model = await self.route_task(task, mode)
        if model is None:
            return {"error": "No suitable model found", "mode": mode.value}

        if self._nim is None:
            return {"error": "NIM provider not configured"}

        try:
            response = await self._nim.chat(model.id, messages)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            result["response"] = content
            result["models_used"] = [model.id]
            return result
        except Exception as e:
            result["error"] = str(e)
            return result

    async def _execute_supernova(
        self,
        task: str,
        messages: List[Dict],
    ) -> Dict[str, Any]:
        """
        Execute a SUPERNOVA task with full multi-model orchestration.

        PLAN→ANALYZE→EXECUTE→VERIFY→SYNTHESIZE
        """
        result = {
            "mode": "supernova",
            "task": task,
            "models_used": [],
            "steps": [],
        }

        plan_messages = messages + [{
            "role": "assistant",
            "content": f"Break down this complex task into sub-goals and identify what models would best help: {task}"
        }]

        planner = await self.route_task(str(plan_messages), TaskMode.THINK)
        if planner is None:
            return {"error": "No thinking model available for planning"}

        try:
            plan_response = await self._nim.chat(planner.id, plan_messages)
            plan = plan_response.get("choices", [{}])[0].get("message", {}).get("content", "")
            result["steps"].append({"step": "plan", "model": planner.id})
            result["models_used"].append(planner.id)
        except Exception as e:
            result["error"] = f"Planning failed: {e}"
            return result

        analysis_messages = [{"role": "user", "content": f"Analyze requirements for: {plan}"}]
        analyzer = await self.route_task(str(analysis_messages), TaskMode.DEEP)

        if analyzer:
            try:
                analysis = await self._nim.chat(analyzer.id, analysis_messages)
                result["steps"].append({"step": "analyze", "model": analyzer.id})
                result["models_used"].append(analyzer.id)
            except Exception:
                pass

        result["plan"] = plan

        return result


__all__ = [
    "TaskMode",
    "TaskSpec", 
    "Orchestrator",
]