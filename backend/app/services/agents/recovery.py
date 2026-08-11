import inspect
from typing import Any, Callable, Optional

from .contracts import AgentResult


class RecoveryAgent:
    """Bounded recovery for operations whose only effects are read-only."""

    async def run_read_only(
        self,
        operation: Callable[[], Any],
        retry_limit: int = 2,
        on_attempt: Optional[Callable[[int, AgentResult], Any]] = None,
    ) -> AgentResult:
        last_result: Optional[AgentResult] = None
        last_error = ""
        limit = min(2, max(0, int(retry_limit)))

        for attempt in range(1, limit + 1):
            try:
                value = operation()
                if inspect.isawaitable(value):
                    value = await value
            except Exception as exc:
                last_error = str(exc) or exc.__class__.__name__
                last_result = AgentResult(
                    status="failed",
                    summary="The read-only attempt failed.",
                    confidence="low",
                    suggested_next_action="Retry later or use another available read-only source.",
                    error=last_error,
                )
                await self._notify(on_attempt, attempt, last_result)
                continue

            if not isinstance(value, AgentResult):
                invalid_result = AgentResult(
                    status="failed",
                    summary="The read-only operation returned an unsupported result and was not retried.",
                    confidence="low",
                    suggested_next_action="Retry with an operation that returns AgentResult.",
                    error="Read-only recovery requires an AgentResult.",
                )
                await self._notify(on_attempt, attempt, invalid_result)
                return invalid_result

            last_result = value
            await self._notify(on_attempt, attempt, value)
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

    @staticmethod
    async def _notify(
        callback: Optional[Callable[[int, AgentResult], Any]],
        attempt: int,
        result: AgentResult,
    ) -> None:
        if callback is None:
            return
        value = callback(attempt, result)
        if inspect.isawaitable(value):
            await value


__all__ = ["RecoveryAgent"]
