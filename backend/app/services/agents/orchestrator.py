import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from .contracts import AgentResult
from .policy import RESOURCEFUL_RESPONSE_POLICY
from .recovery import RecoveryAgent
from .research import ResearchAgent
from .run_store import AgentRunStore
from .verifier import VerifierAgent


_RESEARCH_PATTERN = re.compile(
    r"\b(?:current|latest|today(?:'s)?|news|price|compare|recommend|research|search|"
    r"look\s+up|find\s+online|buy|best)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PreparedAgentContext:
    agent_kind: str
    context: str
    result: Optional[AgentResult] = None
    run_id: Optional[str] = None


class AgentOrchestrator:
    def __init__(
        self,
        research: Optional[ResearchAgent] = None,
        recovery: Optional[RecoveryAgent] = None,
        verifier: Optional[VerifierAgent] = None,
    ) -> None:
        self.research = research or ResearchAgent()
        self.recovery = recovery or RecoveryAgent()
        self.verifier = verifier or VerifierAgent()

    @staticmethod
    def needs_research(prompt: str) -> bool:
        return bool(_RESEARCH_PATTERN.search(prompt or ""))

    async def prepare(
        self,
        prompt: str,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> PreparedAgentContext:
        if not self.needs_research(prompt):
            return PreparedAgentContext(agent_kind="none", context="")

        store = AgentRunStore(db) if db is not None and user_id is not None else None
        run = None
        if store is not None:
            run = store.start(
                user_id=user_id,
                conversation_id=conversation_id,
                kind="research",
                input_data={"query": prompt},
            )
            store.step(run, "search", "running", detail={"query": prompt}, attempt=1)
            db.commit()

        result = await self.recovery.run_read_only(lambda: self.research.run(prompt), retry_limit=2)
        verified = self.verifier.verify_research(result)

        if store is not None and run is not None:
            store.step(
                run,
                "research",
                result.status,
                detail=self._step_detail(result),
                evidence=(item.to_dict() for item in result.evidence),
                attempt=max(1, self.recovery.last_attempts),
            )
            store.step(
                run,
                "verify",
                verified.status,
                detail=self._step_detail(verified),
                evidence=(item.to_dict() for item in verified.evidence),
                attempt=1,
            )
            if verified.status == "failed":
                store.fail(run, verified.error or verified.summary)
            else:
                store.complete(run, verified.to_dict())
            db.commit()

        return PreparedAgentContext(
            agent_kind="research",
            context=self._context_for(verified),
            result=verified,
            run_id=run.id if run is not None else None,
        )

    @staticmethod
    def _step_detail(result: AgentResult) -> dict:
        return {
            "status": result.status,
            "summary": result.summary,
            "confidence": result.confidence,
            "suggested_next_action": result.suggested_next_action,
            "error": result.error,
        }

    @staticmethod
    def _context_for(result: AgentResult) -> str:
        if not result.evidence:
            next_action = result.suggested_next_action or "Retry research later."
            return (
                f"{RESOURCEFUL_RESPONSE_POLICY}\n\n"
                "Research is unavailable for this prompt. Do not invent current facts or citations.\n"
                f"Suggested next action: {next_action}"
            )

        lines = [RESOURCEFUL_RESPONSE_POLICY, "", "Verified research evidence:"]
        for index, item in enumerate(result.evidence, 1):
            lines.extend(
                [
                    f"{index}. {item.title}",
                    f"   URL: {item.url}",
                    f"   Publisher: {item.publisher or 'Unknown'}",
                ]
            )
            if item.published_at:
                lines.append(f"   Published: {item.published_at}")
            lines.extend(
                [
                    f"   Confidence: {item.confidence}",
                    f"   Excerpt: {item.excerpt_summary}",
                ]
            )
        lines.extend(
            [
                "",
                "Use Markdown citations with the exact URLs above for current claims.",
                f"Overall research confidence: {result.confidence}.",
            ]
        )
        return "\n".join(lines)


__all__ = ["AgentOrchestrator", "PreparedAgentContext"]
