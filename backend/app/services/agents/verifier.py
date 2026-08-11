from urllib.parse import urlsplit

from .contracts import AgentResult


def _valid_evidence_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url):
        return False
    try:
        parsed = urlsplit(url.strip())
        parsed.port
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc and parsed.hostname)


class VerifierAgent:
    """Deterministically validates research evidence without network access."""

    def verify_research(self, result: AgentResult) -> AgentResult:
        unique = []
        seen_urls = set()
        for evidence in result.evidence:
            url = evidence.url.strip() if isinstance(evidence.url, str) else ""
            if not _valid_evidence_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            unique.append(evidence)

        status = result.status
        confidence = result.confidence
        next_action = result.suggested_next_action
        if status == "completed" and not unique:
            status = "partial"
            confidence = "low"
            next_action = "Verify the research with at least one valid HTTP(S) source."

        return AgentResult(
            status=status,
            summary=result.summary,
            evidence=unique,
            confidence=confidence,
            suggested_next_action=next_action,
            error=result.error,
        )


__all__ = ["VerifierAgent"]
