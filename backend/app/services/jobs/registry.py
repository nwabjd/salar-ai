import inspect
from typing import Dict, Optional, Tuple

from .contracts import JobHandler


class JobRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, JobHandler] = {}

    def register(self, kind: str, handler: JobHandler) -> None:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("Job kind must be non-empty")
        if not (
            inspect.iscoroutinefunction(handler)
            or inspect.iscoroutinefunction(getattr(handler, "__call__", None))
        ):
            raise TypeError("Job handler must be async")
        if kind in self._handlers:
            raise ValueError("Job kind is already registered")
        self._handlers[kind] = handler

    def resolve(self, kind: str) -> Optional[JobHandler]:
        return self._handlers.get(kind)

    @property
    def registered_kinds(self) -> Tuple[str, ...]:
        return tuple(self._handlers)
