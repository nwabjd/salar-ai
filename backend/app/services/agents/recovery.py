import inspect
from typing import Any, Callable, Optional

from .contracts import AgentResult


class RecoveryAgent:
    """Bounded recovery for operations whose only effects are read-only."""

    def __init__(self) -> None:
        self.last_attempts = 0

    async def run_read_only(
        self,
        operation: Callable[[], Any],
        retry_limit: int = 2,
    ) -> AgentResult:
        self.last_attempts = 0
        last_result: Optional[AgentResult] = None
        last_error = ""
        limit = max(0, int(retry_limit))

        for _ in range(limit):
            self.last_attempts += 1
            try:
                value = operation()
                if inspect.isawaitable(value):
                    value = await value
            except Exception as exc:
                last_error = str(exc) or exc.__class__.__name__
                continue

            if not isinstance(value, AgentResult):
                return AgentResult(
                    status="failed",
                    summary="The read-only operation returned an unsupported result and was not retried.",
                    confidence="low",
                    suggested_next_action="Retry with an operation that returns AgentResult.",
                    error="Read-only recovery requires an AgentResult.",
                )

            last_result = value
            if value.status != "failed":
                return value
            last_error = value.error or value.summary

        if last_result is not None:
            return AgentResult(
                status="failed",
                summary=last_result.summary or "The read-only operation did not complete.",
                evidence=list(last_result.evidence),
                confidence=last_result.confidence or "low",
                suggested_next_action=(
                    last_result.suggested_next_action
                    or "Retry later or use another available read-only source."
                ),
                error=last_result.error or last_error or "The operation failed.",
            )

        return AgentResult(
            status="failed",
            summary="The read-only operation did not complete.",
            confidence="low",
            suggested_next_action="Retry later or use another available read-only source.",
            error=last_error or "No read-only attempt was made.",
        )


__all__ = ["RecoveryAgent"]
