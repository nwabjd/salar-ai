# backend/app/services/core/brain.py
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .toolspec import ToolRegistry

log = logging.getLogger(__name__)

_INTENT_KINDS = ("chat", "research", "action", "plan", "code", "memory")

_INTENT_RULES = [
    ("code", ["code", "program", "build ", "fix ", "debug", "refactor", "script", "python", "function", "component", "pull request", "commit "], 0.9),
    ("research", ["research", "find online", "look up", "search", "news", "latest", "compare", "price", "sources", "investigate", "what is the current", "today"], 0.85),
    ("plan", ["plan", "roadmap", "steps to", "how to build", "strategy", "launch", "mission", "goal", "milestone", "break down"], 0.85),
    ("memory", ["remember", "store this", "recall", "what did i", "do you remember", "my preference", "my favorite", "set a reminder to remember"], 0.8),
    ("action", ["create", "make", "mkdir", "write file", "create file", "run ", "start ", "stop ", "open ", "send ", "install", "download", "move ", "copy ", "delete ", "start server", "set up"], 0.9),
]

_URL_RE = re.compile(r"https?://[^\s'\"]+")
_PATH_RE = re.compile(r"(?:[\w.\-/\\]+\.[\w]+|[\w]+(?:/[\w.\-]+)+)")
_FILE_WRITE_RE = re.compile(r"(?:write|create)\s+(?:the\s+)?(?:file\s+)?['\"]?([\w.\-/\\]+)['\"]?", re.IGNORECASE)
_FOLDER_RE = re.compile(r"(?:mkdir|create\s+(?:folder|directory))\s+(?:called\s+)?['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE)


@dataclass(frozen=True)
class Intent:
    goal: str
    intent_kind: str = "chat"
    requires_approval: bool = False
    can_parallelize: bool = False
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "intent_kind": self.intent_kind,
            "requires_approval": self.requires_approval,
            "can_parallelize": self.can_parallelize,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PlanStep:
    id: str
    tool_name: str
    args: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    parallelizable: bool = False
    needs_approval: bool = False


@dataclass(frozen=True)
class CorePlan:
    steps: List[PlanStep] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    model: str = "light"
    requires_approval: bool = False
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [{"id": s.id, "tool": s.tool_name, "args": s.args, "description": s.description, "parallelizable": s.parallelizable, "needs_approval": s.needs_approval} for s in self.steps],
            "agents": self.agents,
            "model": self.model,
            "requires_approval": self.requires_approval,
            "confidence": self.confidence,
        }


class CoreBrain:
    def __init__(self, classifier: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None, registry: Optional[ToolRegistry] = None) -> None:
        self.classifier = classifier
        self.registry = registry or ToolRegistry()

    def resolve_intent(self, request: str) -> Intent:
        goal = (request or "").strip()
        lowered = goal.lower()
        matches = [(kind, weight) for kind, signals, weight in _INTENT_RULES if any(sig in lowered for sig in signals)]
        if matches:
            kind, weight = max(matches, key=lambda m: m[1])
            matched_count = sum(1 for k, signals, _ in _INTENT_RULES if k == kind for sig in signals if sig in lowered)
            score = min(weight + 0.02 * matched_count, 0.98)
            return Intent(goal=goal, intent_kind=kind, can_parallelize=(kind in ("research", "plan")), confidence=score)

        if self.classifier is not None:
            try:
                result = self.classifier(goal)
                if result and result.get("intent_kind") in _INTENT_KINDS:
                    return Intent(
                        goal=goal,
                        intent_kind=result["intent_kind"],
                        requires_approval=bool(result.get("requires_approval")),
                        can_parallelize=bool(result.get("can_parallelize")),
                        confidence=float(result.get("confidence", 0.6)),
                    )
            except Exception:
                log.warning("classifier failed; falling back to chat", exc_info=True)

        return Intent(goal=goal, intent_kind="chat", confidence=0.5)

    def plan(self, intent: Intent) -> CorePlan:
        if intent.intent_kind == "action":
            return self._plan_action(intent.goal)
        if intent.intent_kind == "research":
            return self._plan_research(intent.goal)
        if intent.intent_kind == "code":
            return self._plan_code(intent.goal)
        return self._plan_respond(intent)

    def route(self, intent: Intent) -> Dict[str, Any]:
        kind = intent.intent_kind
        model = {"code": "code", "research": "research", "chat": "chat", "memory": "chat", "plan": "research", "action": "chat"}.get(kind, "chat")
        agent_map = {"code": "Coder", "research": "Researcher", "action": "System", "plan": "Researcher", "chat": "", "memory": ""}
        agents = [a for a in ([agent_map.get(kind)] if agent_map.get(kind) else []) if a]
        return {"model": model, "agents": agents}

    def _plan_action(self, goal: str) -> CorePlan:
        url = _URL_RE.search(goal)
        if url:
            step = self._step("open_url", {"url": url.group(0)}, "Open the requested URL", parallelizable=True)
            return CorePlan(steps=[step], agents=["Browser"], model="chat", confidence=0.8)

        folder = _FOLDER_RE.search(goal)
        if folder:
            path = folder.group(1).strip("'\"")
            step = self._step("run_command", {"command": f"mkdir -p {path}"}, f"Create folder {path}", parallelizable=False)
            return CorePlan(steps=[step], agents=["System"], model="chat", confidence=0.85)

        write = _FILE_WRITE_RE.search(goal)
        if write:
            path = write.group(1).strip("'\"")
            content = self._extract_content(goal)
            step = self._step("file_write", {"path": path, "content": content}, f"Write file {path}", parallelizable=False)
            return CorePlan(steps=[step], agents=["File Manager"], model="chat", confidence=0.85)

        run = re.search(r"\b(?:run|execute)\s+(.+)", goal, re.IGNORECASE)
        if run:
            cmd = run.group(1).strip().strip("'\"")
            step = self._step("run_command", {"command": cmd}, f"Run command: {cmd}", parallelizable=False)
            return CorePlan(steps=[step], agents=["System"], model="chat", confidence=0.8)

        step = self._step("send_message", {"message": f"I parsed your request as an action but couldn't map it to a safe tool yet: {goal}"}, "Report inability to act", parallelizable=False)
        return CorePlan(steps=[step], agents=["System"], model="chat", confidence=0.6)

    def _plan_research(self, goal: str) -> CorePlan:
        url = _URL_RE.search(goal)
        steps = []
        if url:
            steps.append(self._step("browse_page", {"url": url.group(0)}, "Browse the requested page", parallelizable=True))
        steps.append(self._step("search_knowledge", {"query": goal}, "Search local knowledge", parallelizable=True))
        steps.append(self._step("send_message", {"message": "research-agent"}, "Aggregate research into a response", parallelizable=False))
        return CorePlan(steps=steps, agents=["Researcher"], model="research", confidence=0.7)

    def _plan_code(self, goal: str) -> CorePlan:
        run = re.search(r"\b(?:run|build|test)\s+(.+)", goal, re.IGNORECASE)
        if run:
            cmd = run.group(1).strip().strip("'\"")
            step = self._step("run_command", {"command": cmd}, f"Run command: {cmd}", parallelizable=False)
            return CorePlan(steps=[step], agents=["Coder"], model="code", confidence=0.8)
        step = self._step("send_message", {"message": "code-agent"}, "Draft code plan response", parallelizable=False)
        return CorePlan(steps=[step], agents=["Coder"], model="code", confidence=0.65)

    def _plan_respond(self, intent: Intent) -> CorePlan:
        step = self._step("send_message", {"message": intent.goal}, "Respond to the request", parallelizable=False)
        agents = [] if intent.intent_kind in ("chat", "memory") else ["Researcher"]
        model = "research" if intent.intent_kind in ("plan", "research") else "chat"
        return CorePlan(steps=[step], agents=agents, model=model, confidence=intent.confidence)

    def _step(self, tool_name: str, args: Dict[str, Any], description: str, parallelizable: bool = False) -> PlanStep:
        spec = self.registry.spec(tool_name)
        return PlanStep(id="s1", tool_name=tool_name, args=args, description=description, parallelizable=parallelizable, needs_approval=spec.requires_approval)

    @staticmethod
    def _extract_content(goal: str) -> str:
        for marker in ("with content", "containing", "that says", "content:"):
            idx = goal.lower().find(marker)
            if idx != -1:
                return goal[idx + len(marker):].strip().strip("'\"")
        return ""
