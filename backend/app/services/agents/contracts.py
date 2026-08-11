from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EvidenceSource:
    title: str
    url: str
    excerpt_summary: str
    publisher: str = ""
    published_at: Optional[str] = None
    confidence: str = "low"
    retrieved_at: str = field(default_factory=utc_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AgentAssignment:
    kind: str
    intent: str
    expected_output: str
    allowed_tools: List[str]
    requires_evidence: bool = True
    retry_limit: int = 2


@dataclass
class AgentResult:
    status: str
    summary: str
    evidence: List[EvidenceSource] = field(default_factory=list)
    confidence: str = "low"
    suggested_next_action: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "evidence": [source.to_dict() for source in self.evidence],
            "confidence": self.confidence,
            "suggested_next_action": self.suggested_next_action,
            "error": self.error,
        }
