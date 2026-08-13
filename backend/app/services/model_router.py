import re
from copy import deepcopy

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

    def capability_for(self, query, *, content_type="", complexity="simple"):
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

    def route(self, query, *, content_type="", complexity="simple"):
        cap = self.capability_for(query, content_type=content_type, complexity=complexity)
        return self.model_for(cap)

    def route_for_tools(self, tool_names, query=""):
        tools = {str(t).lower() for t in (tool_names or [])}
        if tools & _CODE_TOOLS:
            return self.model_for("code")
        if tools & _VISION_TOOLS:
            return self.model_for("vision")
        return self.route(query)

    def model_for(self, capability):
        models = self._registry.get(capability)
        if not models:
            raise ModelRouterError(f"No models registered for capability: {capability}")
        return models[0]
