# SALAR Agent Foundation and WhatsApp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1 of the approved SALAR agent platform: durable hidden-agent runs, structured cited research, deterministic verification and recovery, one shared resourceful-response policy, and permanent per-contact WhatsApp introduction memory.

**Architecture:** Add a focused `services/agents` package containing contracts, run persistence, Research, Verifier, Recovery, and Orchestrator. The three existing chat paths use the same prepared research context, while WhatsApp uses a separate contact-state repository backed by a new table. Only new tables are introduced, so the existing SQLAlchemy `Base.metadata.create_all` startup path can deploy without altering existing production tables.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2, Gemini REST client, httpx, DDGS, pytest, SQLite tests, Render deployment.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `backend/app/services/agents/contracts.py` | Typed hidden-agent assignments, evidence, and results. |
| `backend/app/services/agents/run_store.py` | Durable run and step transitions. |
| `backend/app/services/agents/research.py` | Structured web research from DDGS results. |
| `backend/app/services/agents/verifier.py` | Deterministic evidence validation; performs no external actions. |
| `backend/app/services/agents/recovery.py` | Bounded retry for safe read-only specialist work. |
| `backend/app/services/agents/orchestrator.py` | Intent routing and research context preparation. |
| `backend/app/services/agents/policy.py` | Shared resourceful-response and evidence policy. |
| `backend/app/services/browser.py` | Existing bounded page fetcher used to inspect the strongest research results. |
| `backend/app/services/whatsapp_conversations.py` | Per-owner/contact introduction and recent-turn state. |
| `backend/app/models.py` | New `AgentRun`, `AgentRunStep`, and `WhatsAppContactState` tables. |
| `backend/app/main.py` | Initialize the shared hidden-agent orchestrator. |
| `backend/app/services/searcher.py` | Preserve text search compatibility and add structured search output. |
| `backend/app/services/coordinator.py` | Consume prepared research context and shared policy. |
| `backend/app/api/chat.py` | Use one orchestration path for standard and streaming chat. |
| `backend/app/api/agent.py` | Use the same orchestration path for tool-enabled agent chat. |
| `backend/app/api/whatsapp.py` | Load and persist contact state around successful auto-replies. |

### Task 1: Add agent contracts and durable run tables

**Files:**
- Create: `backend/app/services/agents/__init__.py`
- Create: `backend/app/services/agents/contracts.py`
- Create: `backend/app/services/agents/run_store.py`
- Modify: `backend/app/models.py`
- Create: `backend/tests/test_agent_run_store.py`

- [ ] **Step 1: Write the failing run-store test**

```python
# backend/tests/test_agent_run_store.py
import json

from sqlalchemy import select

from app.models import AgentRun, AgentRunStep, User
from app.services.agents.run_store import AgentRunStore


def test_agent_run_store_records_status_steps_and_evidence(client, exchange):
    headers = exchange("researcher@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == me["id"]))
        store = AgentRunStore(db)
        run = store.start(user.id, None, "research", {"query": "latest Gemini Live docs"})
        store.step(run, "search", "running", attempt=1)
        store.step(run, "search", "completed", evidence=[{"url": "https://ai.google.dev/api/live"}], attempt=1)
        store.complete(run, {"summary": "Found official documentation"})
        db.commit()

        saved = db.get(AgentRun, run.id)
        steps = list(db.scalars(
            select(AgentRunStep)
            .where(AgentRunStep.run_id == run.id)
            .order_by(AgentRunStep.created_at, AgentRunStep.id)
        ))

    assert saved.status == "completed"
    assert json.loads(saved.output_json)["summary"] == "Found official documentation"
    assert [(item.name, item.status) for item in steps] == [
        ("search", "running"),
        ("search", "completed"),
    ]
    assert json.loads(steps[-1].evidence_json)[0]["url"] == "https://ai.google.dev/api/live"
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd backend && python -m pytest tests/test_agent_run_store.py -q`

Expected: collection fails because `AgentRun`, `AgentRunStep`, and `AgentRunStore` do not exist.

- [ ] **Step 3: Add the contracts**

```python
# backend/app/services/agents/__init__.py
from .contracts import AgentAssignment, AgentResult, EvidenceSource

__all__ = [
    "AgentAssignment",
    "AgentResult",
    "EvidenceSource",
]
```

Keep this initial package file limited to contracts. `orchestrator.py` does not exist until Task 3, so importing it here would break Task 1 test collection.

```python
# backend/app/services/agents/contracts.py
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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

    def to_dict(self) -> Dict[str, Any]:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "suggested_next_action": self.suggested_next_action,
            "error": self.error,
        }
```

- [ ] **Step 4: Add the new tables without modifying existing tables**

Add `UniqueConstraint` to the SQLAlchemy imports in `backend/app/models.py`, then append:

```python
class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    output_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

- [ ] **Step 5: Implement the run store**

```python
# backend/app/services/agents/run_store.py
import json
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from ...models import AgentRun, AgentRunStep


class AgentRunStore:
    def __init__(self, db: Session):
        self.db = db

    def start(
        self,
        user_id: str,
        conversation_id: Optional[str],
        kind: str,
        input_data: Dict[str, Any],
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            conversation_id=conversation_id,
            kind=kind,
            status="running",
            input_json=json.dumps(input_data),
        )
        self.db.add(run)
        self.db.flush()
        return run

    def step(
        self,
        run: AgentRun,
        name: str,
        status: str,
        detail: Optional[Dict[str, Any]] = None,
        evidence: Optional[Iterable[Dict[str, Any]]] = None,
        attempt: int = 1,
    ) -> AgentRunStep:
        item = AgentRunStep(
            run_id=run.id,
            name=name,
            status=status,
            attempt=attempt,
            detail_json=json.dumps(detail or {}),
            evidence_json=json.dumps(list(evidence or [])),
        )
        self.db.add(item)
        self.db.flush()
        return item

    def complete(self, run: AgentRun, output: Dict[str, Any]) -> None:
        run.status = "completed"
        run.output_json = json.dumps(output)
        run.error = ""
        self.db.flush()

    def fail(self, run: AgentRun, error: str) -> None:
        run.status = "failed"
        run.error = error[:1000]
        self.db.flush()
```

- [ ] **Step 6: Run the focused test and verify GREEN**

Run: `cd backend && python -m pytest tests/test_agent_run_store.py -q`

Expected: `1 passed`.

- [ ] **Step 7: Commit Task 1**

```bash
git add backend/app/models.py backend/app/services/agents backend/tests/test_agent_run_store.py
git commit -m "feat(agents): add durable run ledger"
```

### Task 2: Return structured web evidence while preserving compatibility

**Files:**
- Modify: `backend/app/services/searcher.py`
- Create: `backend/tests/test_searcher.py`

- [ ] **Step 1: Write failing structured-search tests**

```python
# backend/tests/test_searcher.py
from app.services import searcher


class FakeDDGS:
    def text(self, query, max_results):
        assert query == "Gemini Live API"
        assert max_results == 2
        return [
            {
                "title": "Live API",
                "body": "Official bidirectional streaming documentation.",
                "href": "https://ai.google.dev/api/live",
                "date": "2026-08-01",
            },
            {
                "title": "Capabilities",
                "body": "Live API capability guide.",
                "href": "https://ai.google.dev/gemini-api/docs/live-api/capabilities",
            },
        ]


def test_search_web_results_returns_normalized_sources(monkeypatch):
    monkeypatch.setattr(searcher, "DDGS", FakeDDGS)
    results = searcher.search_web_results("Gemini Live API", max_results=2)
    assert results == [
        {
            "title": "Live API",
            "snippet": "Official bidirectional streaming documentation.",
            "url": "https://ai.google.dev/api/live",
            "published_at": "2026-08-01",
        },
        {
            "title": "Capabilities",
            "snippet": "Live API capability guide.",
            "url": "https://ai.google.dev/gemini-api/docs/live-api/capabilities",
            "published_at": None,
        },
    ]


def test_search_web_keeps_existing_text_contract(monkeypatch):
    monkeypatch.setattr(searcher, "DDGS", FakeDDGS)
    output = searcher.search_web("Gemini Live API", max_results=2)
    assert "Live API: Official bidirectional streaming documentation." in output
    assert "https://ai.google.dev/api/live" in output
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd backend && python -m pytest tests/test_searcher.py -q`

Expected: failure because `search_web_results` is not defined.

- [ ] **Step 3: Implement normalized structured results**

Replace `backend/app/services/searcher.py` with:

```python
from typing import Dict, List, Optional

from ddgs import DDGS


def search_web_results(query: str, max_results: int = 5) -> List[Dict[str, Optional[str]]]:
    try:
        results = list(DDGS().text(query, max_results=max_results))
    except Exception:
        return []
    normalized = []
    for item in results:
        url = str(item.get("href") or item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            continue
        normalized.append({
            "title": str(item.get("title") or url).strip(),
            "snippet": str(item.get("body") or item.get("snippet") or "").strip(),
            "url": url,
            "published_at": item.get("date") or item.get("published_at"),
        })
    return normalized


def search_web(query: str, max_results: int = 5) -> str:
    lines = []
    for item in search_web_results(query, max_results=max_results):
        lines.append(f"{item['title']}: {item['snippet']} ({item['url']})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `cd backend && python -m pytest tests/test_searcher.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/services/searcher.py backend/tests/test_searcher.py
git commit -m "feat(research): return structured web evidence"
```

### Task 3: Implement Research, Verifier, Recovery, and routing

**Files:**
- Create: `backend/app/services/agents/research.py`
- Create: `backend/app/services/agents/verifier.py`
- Create: `backend/app/services/agents/recovery.py`
- Create: `backend/app/services/agents/orchestrator.py`
- Create: `backend/app/services/agents/policy.py`
- Create: `backend/tests/test_agent_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

```python
# backend/tests/test_agent_orchestrator.py
import pytest

from app.services.agents.contracts import AgentResult, EvidenceSource
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from app.services.agents.research import ResearchAgent


class FakeResearch:
    def __init__(self, result):
        self.result = result
        self.queries = []

    async def run(self, query):
        self.queries.append(query)
        return self.result


@pytest.mark.asyncio
async def test_orchestrator_routes_current_questions_to_verified_research():
    source = EvidenceSource(
        title="Live API",
        url="https://ai.google.dev/api/live",
        excerpt_summary="Official Live API reference.",
        confidence="high",
    )
    research = FakeResearch(AgentResult(status="completed", summary="Gemini Live is current.", evidence=[source]))
    orchestrator = AgentOrchestrator(research=research)

    prepared = await orchestrator.prepare("What is the latest Gemini Live API behavior?")

    assert prepared.agent_kind == "research"
    assert research.queries == ["What is the latest Gemini Live API behavior?"]
    assert "[1] Live API" in prepared.context
    assert "https://ai.google.dev/api/live" in prepared.context


@pytest.mark.asyncio
async def test_research_opens_strong_results_and_reports_confidence():
    rows = [
        {"title": "Official Live API", "url": "https://ai.google.dev/api/live", "snippet": "API reference", "published_at": None},
        {"title": "Release notes", "url": "https://developers.googleblog.com/live", "snippet": "Release summary", "published_at": "2026-08-01"},
    ]
    opened = []

    def read_page(url):
        opened.append(url)
        return {"status": 200, "title": "Opened source", "text": "Verified page text " * 30}

    agent = ResearchAgent(search=lambda query, limit: rows, read_page=read_page)
    result = await agent.run("latest Gemini Live")

    assert opened == [row["url"] for row in rows]
    assert result.confidence == "high"
    assert all(source.confidence == "high" for source in result.evidence)
    assert result.evidence[0].excerpt_summary.startswith("Verified page text")


@pytest.mark.asyncio
async def test_orchestrator_skips_web_for_private_local_requests():
    research = FakeResearch(AgentResult(status="completed", summary="unused"))
    orchestrator = AgentOrchestrator(research=research)
    prepared = await orchestrator.prepare("Open my downloads folder")
    assert prepared.agent_kind == "none"
    assert prepared.context == ""
    assert research.queries == []


def test_resourceful_policy_requires_truthful_next_actions():
    assert "try an available tool" in RESOURCEFUL_RESPONSE_POLICY
    assert "Never invent" in RESOURCEFUL_RESPONSE_POLICY
    assert "unsafe" in RESOURCEFUL_RESPONSE_POLICY
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend && python -m pytest tests/test_agent_orchestrator.py -q`

Expected: import failures because the specialist modules do not exist.

- [ ] **Step 3: Implement the shared policy**

```python
# backend/app/services/agents/policy.py
RESOURCEFUL_RESPONSE_POLICY = (
    "RESOURCEFUL RESPONSE POLICY:\n"
    "- For an actionable request, try an available tool before declining.\n"
    "- If one route fails, offer or try the safest useful alternative.\n"
    "- If required information is missing, ask one focused question.\n"
    "- State the exact blocker and next action when login, approval, unavailable access, or user intervention is required.\n"
    "- Never invent sources, tool results, sent messages, changed files, purchases, or completed actions.\n"
    "- Decline illegal, unsafe, deceptive, privacy-invasive, or unauthorized actions and offer a safe alternative."
)
```

- [ ] **Step 4: Implement bounded recovery and verification**

```python
# backend/app/services/agents/recovery.py
import asyncio
from typing import Awaitable, Callable

from .contracts import AgentResult


class RecoveryAgent:
    async def run_read_only(
        self,
        operation: Callable[[], Awaitable[AgentResult]],
        retry_limit: int = 2,
    ) -> AgentResult:
        last_error = ""
        for attempt in range(1, retry_limit + 1):
            try:
                result = await operation()
                if result.status != "failed":
                    return result
                last_error = result.error
            except Exception as exc:
                last_error = str(exc)
            if attempt < retry_limit:
                await asyncio.sleep(0)
        return AgentResult(
            status="failed",
            summary="Web research could not be completed.",
            suggested_next_action="Try again or provide a specific source to inspect.",
            error=last_error,
        )
```

```python
# backend/app/services/agents/verifier.py
from urllib.parse import urlparse

from .contracts import AgentResult


class VerifierAgent:
    def verify_research(self, result: AgentResult) -> AgentResult:
        valid = []
        seen = set()
        for source in result.evidence:
            parsed = urlparse(source.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or source.url in seen:
                continue
            seen.add(source.url)
            valid.append(source)
        result.evidence = valid
        if result.status == "completed" and not valid:
            result.status = "partial"
            result.suggested_next_action = "Verify against a named source before relying on this answer."
        return result
```

- [ ] **Step 5: Implement the Research Agent**

```python
# backend/app/services/agents/research.py
import asyncio
from typing import Callable, List
from urllib.parse import urlparse

from ..browser import WebBrowser
from ..searcher import search_web_results
from .contracts import AgentResult, EvidenceSource


class ResearchAgent:
    def __init__(self, search: Callable = search_web_results, read_page: Callable = None):
        self.search = search
        self.read_page = read_page or self._read_page

    @staticmethod
    def _read_page(url: str) -> dict:
        browser = WebBrowser()
        try:
            return browser.fetch_page(url)
        finally:
            browser.close()

    async def run(self, query: str) -> AgentResult:
        rows: List[dict] = await asyncio.to_thread(self.search, query, 6)
        strongest = rows[:3]
        opened = await asyncio.gather(*[
            asyncio.to_thread(self.read_page, row["url"])
            for row in strongest
        ])
        evidence = []
        for index, row in enumerate(rows):
            publisher = urlparse(row["url"]).netloc.removeprefix("www.")
            page = opened[index] if index < len(opened) else {}
            page_text = " ".join((page.get("text") or "").split())
            opened_ok = page.get("status") == 200 and len(page_text) >= 120
            evidence.append(EvidenceSource(
                title=page.get("title") or row["title"],
                url=row["url"],
                excerpt_summary=(page_text[:600] if opened_ok else row["snippet"]),
                publisher=publisher,
                published_at=row.get("published_at"),
                confidence="high" if opened_ok else "low",
            ))
        if not evidence:
            return AgentResult(
                status="failed",
                summary="No reliable web results were returned.",
                confidence="low",
                suggested_next_action="Try a narrower query or provide a source URL.",
                error="no_results",
            )
        opened_publishers = {item.publisher for item in evidence if item.confidence == "high"}
        confidence = "high" if len(opened_publishers) >= 2 else "medium" if opened_publishers else "low"
        return AgentResult(
            status="completed",
            summary=f"Collected {len(evidence)} web sources.",
            evidence=evidence,
            confidence=confidence,
        )
```

- [ ] **Step 6: Implement deterministic routing and formatted evidence**

```python
# backend/app/services/agents/orchestrator.py
from dataclasses import dataclass
import re
from typing import Optional

from sqlalchemy.orm import Session

from .contracts import AgentResult
from .recovery import RecoveryAgent
from .research import ResearchAgent
from .run_store import AgentRunStore
from .verifier import VerifierAgent


RESEARCH_PATTERN = re.compile(
    r"\b(latest|current|today|news|price|compare|recommend|research|search|look up|find online|buy|best)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PreparedAgentContext:
    agent_kind: str
    context: str
    result: Optional[AgentResult] = None
    run_id: Optional[str] = None


class AgentOrchestrator:
    def __init__(self, research=None, verifier=None, recovery=None):
        self.research = research or ResearchAgent()
        self.verifier = verifier or VerifierAgent()
        self.recovery = recovery or RecoveryAgent()

    def needs_research(self, prompt: str) -> bool:
        return bool(RESEARCH_PATTERN.search(prompt))

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
        run = store.start(user_id, conversation_id, "research", {"query": prompt}) if store else None
        if store and run:
            store.step(run, "search", "running", attempt=1)

        result = await self.recovery.run_read_only(lambda: self.research.run(prompt), retry_limit=2)
        result = self.verifier.verify_research(result)

        if store and run:
            store.step(
                run,
                "search",
                result.status,
                evidence=[item.to_dict() for item in result.evidence],
                attempt=1,
            )
            if result.status == "failed":
                store.fail(run, result.error)
            else:
                store.complete(run, result.to_dict())

        context = self.format_research_context(result)
        return PreparedAgentContext(
            agent_kind="research",
            context=context,
            result=result,
            run_id=run.id if run else None,
        )

    @staticmethod
    def format_research_context(result: AgentResult) -> str:
        if not result.evidence:
            return (
                "Research status: unavailable. Do not invent current facts or citations. "
                f"Next action: {result.suggested_next_action}"
            )
        lines = [
            "Verified web research. Cite supporting claims with Markdown links using these exact URLs:",
        ]
        for index, source in enumerate(result.evidence, 1):
            date = f"; published {source.published_at}" if source.published_at else ""
            lines.append(
                f"[{index}] {source.title} — {source.excerpt_summary} "
                f"({source.url}{date}; confidence {source.confidence})"
            )
        return "\n".join(lines)
```

After creating `orchestrator.py`, update the package exports:

```python
# backend/app/services/agents/__init__.py
from .contracts import AgentAssignment, AgentResult, EvidenceSource
from .orchestrator import AgentOrchestrator, PreparedAgentContext

__all__ = [
    "AgentAssignment",
    "AgentResult",
    "EvidenceSource",
    "AgentOrchestrator",
    "PreparedAgentContext",
]
```

- [ ] **Step 7: Run the focused tests and verify GREEN**

Run: `cd backend && python -m pytest tests/test_agent_orchestrator.py -q`

Expected: `4 passed`.

- [ ] **Step 8: Commit Task 3**

```bash
git add backend/app/services/agents backend/tests/test_agent_orchestrator.py
git commit -m "feat(agents): add research verification and recovery"
```

### Task 4: Route every chat path through the shared agent context

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/coordinator.py`
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/agent.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_chat.py`
- Create: `backend/tests/test_agent_prompting.py`

- [ ] **Step 1: Write failing prompt and endpoint tests**

```python
# backend/tests/test_agent_prompting.py
from app.api.agent import _build_agent_system_prompt
from app.services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from app.services.coordinator import AICoordinator


class FakeGemini:
    pass


def test_coordinator_payload_contains_shared_policy_and_cited_context():
    coordinator = AICoordinator(FakeGemini())
    payload = coordinator.build_payload(
        prompt="What is current?",
        messages=[],
        memories=[],
        documents=[],
        agent_context="[1] Official source (https://example.com/current)",
    )
    system = payload[0]["content"]
    assert RESOURCEFUL_RESPONSE_POLICY in system
    assert "https://example.com/current" in system


def test_tool_agent_prompt_uses_same_resourceful_policy():
    prompt = _build_agent_system_prompt([], [], "[1] Source (https://example.com)")
    assert RESOURCEFUL_RESPONSE_POLICY in prompt
    assert "https://example.com" in prompt
```

Append to `backend/tests/test_chat.py`:

```python
def test_chat_threads_user_and_conversation_into_agent_preparation(client, auth_headers):
    created = client.post("/api/conversations", json={"title": "Research"}, headers=auth_headers)
    conversation_id = created.json()["id"]

    reply = client.post(
        "/api/chat",
        json={"conversation_id": conversation_id, "content": "What is the latest Gemini Live API?"},
        headers=auth_headers,
    )

    assert reply.status_code == 200
    prepared = client.app.state.agent_orchestrator.calls[-1]
    assert prepared["prompt"] == "What is the latest Gemini Live API?"
    assert prepared["conversation_id"] == conversation_id
    assert prepared["user_id"]
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend && python -m pytest tests/test_agent_prompting.py tests/test_chat.py -q`

Expected: failures because `agent_context` and `agent_orchestrator` are not wired.

- [ ] **Step 3: Add a fake orchestrator to the test app**

Update `backend/tests/conftest.py`:

```python
from app.services.agents.orchestrator import PreparedAgentContext


class FakeAgentOrchestrator:
    def __init__(self):
        self.calls = []

    async def prepare(self, prompt, db=None, user_id=None, conversation_id=None):
        self.calls.append({
            "prompt": prompt,
            "user_id": user_id,
            "conversation_id": conversation_id,
        })
        return PreparedAgentContext(agent_kind="none", context="")
```

In the `client` fixture, after assigning `FakeCoordinator`, assign:

```python
app.state.agent_orchestrator = FakeAgentOrchestrator()
```

Change `FakeCoordinator.reply` to accept the prepared context:

```python
class FakeCoordinator:
    async def reply(self, *, prompt, messages, memories, documents, agent_context=""):
        return f"Test response to: {prompt}"
```

- [ ] **Step 4: Initialize the production orchestrator**

In `backend/app/main.py`, import `AgentOrchestrator` and set it during lifespan only when a test has not injected one:

```python
from .services.agents.orchestrator import AgentOrchestrator
```

```python
if not hasattr(app.state, "agent_orchestrator"):
    app.state.agent_orchestrator = AgentOrchestrator()
```

- [ ] **Step 5: Centralize the shared policy in coordinator payloads**

In `backend/app/services/coordinator.py`, import `RESOURCEFUL_RESPONSE_POLICY`, rename the `search_results` parameter to `agent_context`, and use:

```python
from .agents.policy import RESOURCEFUL_RESPONSE_POLICY
```

```python
def build_payload(self, *, prompt: str, messages: Iterable, memories: Iterable, documents: Iterable, agent_context: str = "") -> list:
    context_parts = []
    memory_text = "\n".join(f"- {item.title}: {item.content}" for item in memories)
    if memory_text:
        context_parts.append(f"Relevant saved memory:\n{memory_text}")
    document_text = "\n".join(f"- {item.filename}: {_safe_extract_text(item)}" for item in documents)
    if document_text:
        context_parts.append(f"Relevant documents:\n{document_text}")
    if agent_context:
        context_parts.append(agent_context)

    system = SYSTEM_PROMPT + "\n\n" + RESOURCEFUL_RESPONSE_POLICY
    if context_parts:
        system += "\n\n" + "\n\n".join(context_parts)
    payload = [{"role": "system", "content": system}]
    payload.extend({"role": item.role, "content": item.content} for item in list(messages)[-16:])
    payload.append({"role": "user", "content": prompt})
    return payload
```

Replace `reply` with a version that does not perform its own duplicate search:

```python
async def reply(self, *, prompt: str, messages: Iterable, memories: Iterable, documents: Iterable, agent_context: str = "") -> str:
    payload = self.build_payload(
        prompt=prompt,
        messages=messages,
        memories=memories,
        documents=documents,
        agent_context=agent_context,
    )
    try:
        return await self.gemini.chat(payload)
    except Exception as e:
        log.error("Gemini request failed: %s", e)
        return "I'm having trouble connecting to the AI service. Your message was saved — please try again in a moment."
```

- [ ] **Step 6: Prepare context in standard chat**

In `/api/chat`, before `coordinator.reply`, add:

```python
prepared = await request.app.state.agent_orchestrator.prepare(
    prompt,
    db=db,
    user_id=user.id,
    conversation_id=conversation.id,
)
```

Pass `agent_context=prepared.context` into `coordinator.reply`, and include `"agent_run_id": prepared.run_id` in the `chat.completed` audit JSON.

The existing final `db.commit()` must commit the message, audit event, and agent ledger atomically. On a request error, use the existing rollback/error path so a partial agent run is not reported as a completed chat.

- [ ] **Step 7: Prepare the same context in streaming chat**

Before defining `generate()`, call the same `agent_orchestrator.prepare` function for non-fast requests. For the `fast` Live-voice branch, use `PreparedAgentContext(agent_kind="none", context="")` so web search cannot add latency to the realtime response path. Remove `_search_with_timeout` and the duplicate `search_results` assembly. Build the non-fast `agent_system` from the coordinator payload so memories, documents, policy, and prepared evidence cannot drift between chat paths:

```python
prepared = (
    PreparedAgentContext(agent_kind="none", context="")
    if payload.fast
    else await request.app.state.agent_orchestrator.prepare(
        payload.content,
        db=db,
        user_id=user.id,
        conversation_id=conversation.id,
    )
)

agent_system = coordinator.build_payload(
    prompt=payload.content,
    messages=history,
    memories=memories,
    documents=documents,
    agent_context=prepared.context,
)[0]["content"]
agent_system += (
    "\n\nUse available tools for actionable requests and summarize every tool result "
    "in natural language."
)
```

For the fast branch, pass the same `RESOURCEFUL_RESPONSE_POLICY` to Gemini without research context. Add `agent_run_id` to the final audit event, and commit the agent ledger in the generator's existing successful transaction. If the client disconnects or generation fails, record a failed/cancelled audit outcome rather than a successful run.

- [ ] **Step 8: Prepare the same context in `/api/agent`**

In `backend/app/api/agent.py`, import `RESOURCEFUL_RESPONSE_POLICY`, call `agent_orchestrator.prepare` with the current session/user/conversation, pass `prepared.context` to `_build_agent_system_prompt`, and append `RESOURCEFUL_RESPONSE_POLICY` inside that prompt. Add `agent_run_id` to `agent.completed` audit JSON.

- [ ] **Step 9: Run focused integration tests and verify GREEN**

Run: `cd backend && python -m pytest tests/test_agent_prompting.py tests/test_chat.py -q`

Expected: all tests pass.

- [ ] **Step 10: Commit Task 4**

```bash
git add backend/app/main.py backend/app/services/coordinator.py backend/app/api/chat.py backend/app/api/agent.py backend/tests/conftest.py backend/tests/test_chat.py backend/tests/test_agent_prompting.py
git commit -m "feat(agents): route chat through hidden specialists"
```

### Task 5: Persist one-time WhatsApp introductions and recent contact history

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/whatsapp_conversations.py`
- Modify: `backend/app/api/whatsapp.py`
- Modify: `backend/tests/test_whatsapp_assistant.py`
- Modify: `backend/tests/test_isolation.py`

- [ ] **Step 1: Write failing WhatsApp conversation tests**

Replace the prompt test and append state tests in `backend/tests/test_whatsapp_assistant.py`:

```python
from sqlalchemy import select

from types import SimpleNamespace

import pytest
from app.api.whatsapp import _auto_reply, build_auto_reply_messages, normalize_auto_reply
from app.models import User, WhatsAppContactState
from app.services.whatsapp_conversations import WhatsAppConversationStore


def test_whatsapp_first_reply_introduces_jds_assistant():
    messages = build_auto_reply_messages("Aisha", "Hello", False, introduced=False, history=[])
    assert "introduce yourself briefly as JD's assistant" in messages[0]["content"]


def test_whatsapp_later_reply_forbids_reintroduction_and_includes_history():
    history = [
        {"role": "sender", "text": "Can JD review the proposal?"},
        {"role": "assistant", "text": "Certainly. What deadline are you working with?"},
    ]
    messages = build_auto_reply_messages("Aisha", "Tomorrow", False, introduced=True, history=history)
    prompt = messages[0]["content"]
    assert "Never introduce yourself again" in prompt
    assert "Can JD review the proposal?" in prompt
    assert "What deadline are you working with?" in prompt


def test_whatsapp_fallback_does_not_repeat_introduction():
    first, _ = normalize_auto_reply("", introduced=False)
    later, _ = normalize_auto_reply("", introduced=True)
    assert first.startswith("Hello, this is JD's assistant")
    assert later == "How may I help you?"


def test_whatsapp_first_reply_enforces_introduction_if_model_omits_it():
    reply, _ = normalize_auto_reply("Your delivery is scheduled for Tuesday.", introduced=False)
    assert reply == "Hello, this is JD's assistant. Your delivery is scheduled for Tuesday."


def test_whatsapp_later_reply_strips_a_repeated_model_introduction():
    reply, _ = normalize_auto_reply(
        "Hello, this is JD's assistant. Your delivery is scheduled for Tuesday.",
        introduced=True,
    )
    assert reply == "Your delivery is scheduled for Tuesday."


def test_contact_state_is_per_owner_and_contact(client, exchange):
    headers_a = exchange("owner-a@example.com")
    headers_b = exchange("owner-b@example.com")
    user_a = client.get("/api/auth/me", headers=headers_a).json()
    user_b = client.get("/api/auth/me", headers=headers_b).json()

    with client.app.state.SessionLocal() as db:
        owner_a = db.scalar(select(User).where(User.id == user_a["id"]))
        owner_b = db.scalar(select(User).where(User.id == user_b["id"]))
        store = WhatsAppConversationStore(db)
        state_a = store.get_or_create(owner_a.id, "15550001@s.whatsapp.net", "Aisha")
        state_b = store.get_or_create(owner_b.id, "15550001@s.whatsapp.net", "Aisha")
        store.record_exchange(state_a, "Hello", "Hello, this is JD's assistant.", introduced=True)
        db.commit()

        saved_a = db.get(WhatsAppContactState, state_a.id)
        saved_b = db.get(WhatsAppContactState, state_b.id)

    assert saved_a.introduced is True
    assert saved_b.introduced is False


@pytest.mark.anyio
async def test_failed_send_does_not_mark_contact_introduced(client, exchange):
    headers = exchange("failed-send@example.com")
    user = client.get("/api/auth/me", headers=headers).json()

    class FakeGemini:
        async def chat_with_tools(self, messages, tools):
            return {"text": "Hello, this is JD's assistant. How may I help?"}

    class FailingWhatsApp:
        async def send_message(self, **kwargs):
            return {"error": "offline"}

    state = SimpleNamespace(
        SessionLocal=client.app.state.SessionLocal,
        coordinator=SimpleNamespace(gemini=FakeGemini()),
        whatsapp=FailingWhatsApp(),
    )
    await _auto_reply(state, user["id"], "15550002@s.whatsapp.net", "Aisha", "Hello", False)

    with client.app.state.SessionLocal() as db:
        saved = db.scalar(select(WhatsAppContactState).where(
            WhatsAppContactState.user_id == user["id"],
            WhatsAppContactState.contact_jid == "15550002@s.whatsapp.net",
        ))
    assert saved is None or saved.introduced is False
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `cd backend && python -m pytest tests/test_whatsapp_assistant.py -q`

Expected: failures because the contact table/store and new helper arguments do not exist.

- [ ] **Step 3: Add the contact-state table**

Append to `backend/app/models.py`:

```python
class WhatsAppContactState(Base):
    __tablename__ = "whatsapp_contact_states"
    __table_args__ = (UniqueConstraint("user_id", "contact_jid", name="uq_whatsapp_owner_contact"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=token_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_jid: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    introduced: Mapped[bool] = mapped_column(Boolean, default=False)
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    active_topic: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
```

- [ ] **Step 4: Implement the contact repository**

```python
# backend/app/services/whatsapp_conversations.py
import json
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import WhatsAppContactState


class WhatsAppConversationStore:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, user_id: str, contact_jid: str, sender_name: str) -> WhatsAppContactState:
        state = self.db.scalar(select(WhatsAppContactState).where(
            WhatsAppContactState.user_id == user_id,
            WhatsAppContactState.contact_jid == contact_jid,
        ))
        if state is None:
            state = WhatsAppContactState(
                user_id=user_id,
                contact_jid=contact_jid,
                sender_name=sender_name,
            )
            self.db.add(state)
            self.db.flush()
        elif sender_name:
            state.sender_name = sender_name
        return state

    @staticmethod
    def history(state: WhatsAppContactState) -> List[Dict[str, str]]:
        try:
            value = json.loads(state.history_json or "[]")
        except json.JSONDecodeError:
            return []
        return [item for item in value if item.get("role") in {"sender", "assistant"} and item.get("text")][-8:]

    def record_exchange(
        self,
        state: WhatsAppContactState,
        incoming: str,
        reply: str,
        introduced: bool,
    ) -> None:
        turns = self.history(state)
        turns.extend([
            {"role": "sender", "text": incoming[:1000]},
            {"role": "assistant", "text": reply[:1000]},
        ])
        state.history_json = json.dumps(turns[-8:])
        state.introduced = state.introduced or introduced
        state.active_topic = incoming[:500]
        self.db.flush()
```

- [ ] **Step 5: Make message construction state-aware**

Change the helper signatures and policy in `backend/app/api/whatsapp.py`:

```python
def build_auto_reply_messages(sender_name: str, text: str, is_group: bool, introduced: bool, history):
    context = f"WhatsApp {'group' if is_group else 'DM'} message from {sender_name}: {text}"
    history_text = "\n".join(f"{item['role']}: {item['text']}" for item in history[-8:])
    identity_rule = (
        "This is the first reply to this contact. Introduce yourself briefly as JD's assistant once, then help."
        if not introduced
        else "This contact already knows you are JD's assistant. Never introduce yourself again; continue naturally from the conversation."
    )
    policy = (
        "You are replying professionally to a WhatsApp sender on JD's behalf. "
        "Never pretend to be JD and never introduce yourself as an AI. "
        f"{identity_rule} "
        "Address specific queries directly. Ask one focused question when essential details are missing. "
        "Do not fabricate facts, promises, availability, prices, dates, or actions. "
        "Use a warm, authentic, professional tone in one to three short plain-text sentences. "
        "If the sender explicitly asks you to tell JD something, respond only with GOTOPASS: followed by the concise message for JD."
    )
    if history_text:
        policy += f"\n\nRecent conversation:\n{history_text}"
    return [{"role": "system", "content": policy}, {"role": "user", "content": context}]


def normalize_auto_reply(reply_text: str, introduced: bool):
    clean = (reply_text or "").strip()
    if not clean:
        clean = "How may I help you?"
    pass_message = None
    if clean.startswith("GOTOPASS:"):
        pass_message = clean[len("GOTOPASS:"):].strip() or None
        clean = "Thank you. I'll make sure JD receives your message. Is there anything else I can help you with?"
    if introduced:
        clean = re.sub(
            r"^(?:hello[,!]?\s*)?(?:this is|i am|i'm)\s+jd(?:'s|s)\s+assistant[.!,:-]*\s*",
            "",
            clean,
            flags=re.IGNORECASE,
        ).strip()
        if not clean:
            clean = "How may I help you?"
    elif not re.search(r"\bjd(?:'s|s)\s+assistant\b", clean, flags=re.IGNORECASE):
        clean = "Hello, this is JD's assistant. " + clean
    return clean, pass_message
```

Add `import re` for the deterministic reintroduction guard. The prompt guides tone; this guard enforces the one-time identity rule even if the model ignores it.

- [ ] **Step 6: Persist state only after a successful send**

In `_auto_reply`, open one database session before building messages, load contact state with `WhatsAppConversationStore`, pass `state.introduced` and `store.history(state)` to the helpers, and inspect the send result. Use this transaction shape:

```python
save_db = state.SessionLocal()
try:
    store = WhatsAppConversationStore(save_db)
    contact = store.get_or_create(user_id, from_jid, sender_name)
    messages = build_auto_reply_messages(sender_name, text, is_group, contact.introduced, store.history(contact))
    result = await gemini.chat_with_tools(messages, [])
    reply_text, pass_msg = normalize_auto_reply(result.get("text", "").strip(), contact.introduced)

    whatsapp = getattr(state, "whatsapp", None)
    if not whatsapp:
        return
    send_result = await whatsapp.send_message(to=from_jid, text=reply_text, user_id=user_id)
    if isinstance(send_result, dict) and send_result.get("error"):
        raise RuntimeError(send_result["error"])

    store.record_exchange(contact, text, reply_text, introduced=True)
    save_db.add(AuditEvent(
        user_id=user_id,
        action="whatsapp.auto_reply",
        detail_json=json.dumps({
            "to": from_jid,
            "sender_name": sender_name,
            "incoming": text[:300],
            "reply": reply_text[:300],
        }),
    ))
    if pass_msg:
        save_db.add(AuditEvent(
            user_id=user_id,
            action="whatsapp.pass_message",
            detail_json=json.dumps({
                "from": from_jid,
                "sender_name": sender_name,
                "message": pass_msg[:500],
                "acknowledged": False,
            }),
        ))
    save_db.commit()
except Exception:
    save_db.rollback()
    raise
finally:
    save_db.close()
```

Import `WhatsAppConversationStore` at the top of `backend/app/api/whatsapp.py`. Keep the existing outer `_auto_reply` exception logger, and remove the old nested `save_db` block so each successful reply is committed once. A missing WhatsApp client, a returned `error`, or a raised send exception must exit through rollback; the failing-send test proves the contact remains unintroduced.

- [ ] **Step 7: Add contact isolation coverage**

Append to `backend/tests/test_isolation.py`:

```python
def test_whatsapp_contact_state_does_not_cross_users(client, exchange):
    from sqlalchemy import select
    from app.models import WhatsAppContactState

    headers_a = exchange("contact-owner-a@example.com")
    headers_b = exchange("contact-owner-b@example.com")
    user_a = client.get("/api/auth/me", headers=headers_a).json()
    user_b = client.get("/api/auth/me", headers=headers_b).json()

    with client.app.state.SessionLocal() as db:
        db.add_all([
            WhatsAppContactState(user_id=user_a["id"], contact_jid="same@s.whatsapp.net", introduced=True),
            WhatsAppContactState(user_id=user_b["id"], contact_jid="same@s.whatsapp.net", introduced=False),
        ])
        db.commit()
        rows = list(db.scalars(select(WhatsAppContactState).where(
            WhatsAppContactState.contact_jid == "same@s.whatsapp.net"
        )))

    assert {(row.user_id, row.introduced) for row in rows} == {
        (user_a["id"], True),
        (user_b["id"], False),
    }
```

- [ ] **Step 8: Run WhatsApp tests and verify GREEN**

Run: `cd backend && python -m pytest tests/test_whatsapp_assistant.py tests/test_isolation.py tests/test_whatsapp_qr.py -q`

Expected: all tests pass.

- [ ] **Step 9: Commit Task 5**

```bash
git add backend/app/models.py backend/app/services/whatsapp_conversations.py backend/app/api/whatsapp.py backend/tests/test_whatsapp_assistant.py backend/tests/test_isolation.py
git commit -m "fix(whatsapp): remember contact introductions"
```

### Task 6: Verify Phase 1 as one deployable backend release

**Files:**
- Modify only if verification exposes a Phase 1 regression.

- [ ] **Step 1: Run all focused Phase 1 tests**

Run:

```powershell
Set-Location backend
python -m pytest tests/test_agent_run_store.py tests/test_searcher.py tests/test_agent_orchestrator.py tests/test_agent_prompting.py tests/test_chat.py tests/test_whatsapp_assistant.py tests/test_isolation.py tests/test_whatsapp_qr.py -q
Set-Location ..
```

Expected: every listed test passes with zero failures.

- [ ] **Step 2: Run the complete backend suite**

Run: `cd backend && python -m pytest -q`

Expected: all backend tests pass with zero failures.

- [ ] **Step 3: Run Python syntax verification**

Run: `cd backend && python -m compileall -q app`

Expected: exit code `0` and no output.

- [ ] **Step 4: Check repository whitespace and scope**

Run:

```bash
git diff --check
git status --short
git log --oneline -6
```

Expected: no whitespace errors; only Phase 1 files are modified or committed; unrelated existing untracked files remain untouched.

- [ ] **Step 5: Push the verified backend release**

Run:

```bash
git push origin main
```

Expected: the Phase 1 commits are pushed to `origin/main`, allowing the connected Render service to deploy them.

- [ ] **Step 6: Verify Render health after deployment**

Run:

```powershell
$taskHealth = Invoke-WebRequest -Uri 'https://salar-backend.onrender.com/api/health' -UseBasicParsing -TimeoutSec 60
[pscustomobject]@{ Status = [int]$taskHealth.StatusCode; Body = $taskHealth.Content } | Format-List
```

Expected: HTTP `200` and `{"status":"ok","service":"salar-backend","version":"0.1.0"}`.

The health endpoint proves service availability but does not expose a commit identifier. Report the pushed commit hashes separately and do not claim Render is running a specific commit without a deployment signal.

## Phase 1 completion criteria

- Research-needed prompts create durable hidden-agent runs and structured evidence.
- Standard chat, non-fast streaming chat, and tool-agent chat receive the same resourceful policy and research context; fast Live voice receives the same policy without web-search latency.
- Research context contains valid source URLs and explicitly forbids invented citations when research fails.
- Verifier performs no external action and downgrades unsupported research.
- Recovery retries only safe read-only work with a strict limit.
- WhatsApp introductions are permanent per owner/contact after the first successfully sent reply.
- Later WhatsApp replies include recent contact history and explicitly forbid reintroduction.
- Failed WhatsApp sends do not mark a contact introduced.
- All user and contact state remains isolated.
- Full backend tests and syntax verification pass before push.
