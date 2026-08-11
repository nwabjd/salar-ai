from dataclasses import replace

from .contracts import AgentResult
from .urls import canonical_hostname, canonical_public_url


def _valid_evidence_url(url: object) -> bool:
    return canonical_public_url(url) is not None


class VerifierAgent:
    """Deterministically validates research evidence without network access."""

    def verify_research(self, result: AgentResult) -> AgentResult:
        unique = []
        seen_urls = set()
        for evidence in result.evidence:
            url = canonical_public_url(evidence.url)
            if url is None or url in seen_urls:
                continue
            seen_urls.add(url)
            evidence_kind = evidence.evidence_kind or (
                "opened_page" if evidence.confidence == "high" else "search_only"
            )
            confidence = evidence.confidence if evidence_kind == "opened_page" else "low"
            unique.append(
                replace(
                    evidence,
                    url=url,
                    publisher=canonical_hostname(url),
                    confidence=confidence,
                    evidence_kind=evidence_kind,
                )
            )

        status = result.status
        next_action = result.suggested_next_action
        high_publishers = {
            evidence.publisher
            for evidence in unique
            if evidence.evidence_kind == "opened_page" and evidence.confidence == "high"
        }
        if len(high_publishers) >= 2:
            confidence = "high"
        elif len(high_publishers) == 1:
            confidence = "medium"
        else:
            confidence = "low"
        if status == "completed" and not unique:
            status = "partial"
            next_action = "Verify the research with at least one valid HTTP(S) source."
        elif status == "completed" and not high_publishers:
            status = "partial"
            next_action = next_action or "Open and verify at least one retained public source."

        return AgentResult(
            status=status,
            summary=result.summary,
            evidence=unique,
            confidence=confidence,
            suggested_next_action=next_action,
            error=result.error,
        )


__all__ = ["VerifierAgent"]
