"""Shared contracts for the durable background job engine."""

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from sqlalchemy.orm import Session

from ...config import Settings

log = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Everything a job handler needs to do its work safely."""

    user_id: str
    job_id: str
    kind: str
    db: Session
    settings: Settings
    input_data: Dict[str, Any]


Handler = Callable[[JobContext], Awaitable[Dict[str, Any]]]


class JobRegistry:
    """Stable kind -> async-handler registry for background jobs."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}

    def register(self, kind: str, handler: Optional[Handler] = None):
        """Register a handler. Usable both as `register(kind, fn)` and
        as a decorator: `@registry.register(kind)`."""
        if handler is None:
            def decorator(fn: Handler) -> Handler:
                self._handlers[kind] = fn
                return fn
            return decorator
        self._handlers[kind] = handler
        return handler

    def get(self, kind: str) -> Optional[Handler]:
        return self._handlers.get(kind)

    def has(self, kind: str) -> bool:
        return kind in self._handlers

    def kinds(self):
        return sorted(self._handlers.keys())


def register_handler(registry: JobRegistry, kind: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        registry.register(kind, handler)
        return handler

    return decorator


def normalize_error(error: BaseException) -> str:
    """Normalize an unexpected error to a bounded, safe message."""
    text = str(error).strip()
    if not text:
        text = error.__class__.__name__
    return text[:1000]
