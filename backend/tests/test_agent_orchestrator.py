import json

import pytest

from app.models import AgentRun, AgentRunStep, User
from app.services.agents.contracts import AgentResult, EvidenceSource
from app.services.agents.orchestrator import AgentOrchestrator, PreparedAgentContext
from app.services.agents.policy import RESOURCEFUL_RESPONSE_POLICY
from app.services.agents.recovery import RecoveryAgent
from app.services.agents.research import ResearchAgent
from app.services.agents.verifier import VerifierAgent


def source(
    url="https://docs.example.com/live",
    *,
    title="Gemini Live API",
    publisher="Example Docs",
    confidence="high",
):
    return EvidenceSource(
        title=title,
        url=url,
        excerpt_summary="The current API documentation describes realtime audio and tool behavior.",
        publisher=publisher,
        published_at="2026-08-01",
        confidence=confidence,
        retrieved_at="2026-08-11T10:00:00+00:00",
    )


class FakeResearch:
    def __init__(self, result):
        self.result = result
        self.queries = []

    async def run(self, query):
        self.queries.append(query)
        return self.result


def test_resourceful_policy_sets_truthful_safe_tool_use_boundaries():
    assert "try an available tool" in RESOURCEFUL_RESPONSE_POLICY
    assert "Never invent" in RESOURCEFUL_RESPONSE_POLICY
    assert "unsafe" in RESOURCEFUL_RESPONSE_POLICY
    assert "prepared" in RESOURCEFUL_RESPONSE_POLICY
    assert "attempted" in RESOURCEFUL_RESPONSE_POLICY
    assert "completed" in RESOURCEFUL_RESPONSE_POLICY


@pytest.mark.asyncio
async def test_orchestrator_routes_current_web_prompt_and_formats_exact_evidence_url():
    result = AgentResult(status="completed", summary="Current behavior found.", evidence=[source()], confidence="high")
    research = FakeResearch(result)
    orchestrator = AgentOrchestrator(research=research)

    prepared = await orchestrator.prepare("What is the latest Gemini Live API behavior?")

    assert isinstance(prepared, PreparedAgentContext)
    assert prepared.agent_kind == "research"
    assert research.queries == ["What is the latest Gemini Live API behavior?"]
    assert "1. Gemini Live API" in prepared.context
    assert "https://docs.example.com/live" in prepared.context
    assert "Markdown citations" in prepared.context


@pytest.mark.asyncio
async def test_orchestrator_skips_unrelated_private_local_prompt():
    research = FakeResearch(AgentResult(status="failed", summary="should not run"))

    prepared = await AgentOrchestrator(research=research).prepare("Open my downloads folder")

    assert prepared.agent_kind == "none"
    assert prepared.context == ""
    assert prepared.result is None
    assert prepared.run_id is None
    assert research.queries == []


@pytest.mark.parametrize(
    "prompt",
    [
        "today's AI news",
        "price of bitcoin",
        "compare current phones",
        "recommend a laptop",
        "research Gemini",
        "search Gemini updates",
        "look up Gemini online",
        "find online stores",
        "where can I buy this?",
        "best current headphones",
    ],
)
def test_orchestrator_research_router_covers_required_intents(prompt):
    assert AgentOrchestrator.needs_research(prompt) is True


@pytest.mark.asyncio
async def test_research_opens_top_results_and_builds_high_confidence_evidence():
    rows = [
        {
            "title": "Official Gemini Live docs",
            "url": "https://ai.google.dev/api/live",
            "snippet": "Official reference",
            "publisher": "Google AI",
            "published_at": "2026-08-01",
        },
        {
            "title": "Gemini Live analysis",
            "url": "https://example.org/gemini-live",
            "snippet": "Independent analysis",
            "publisher": "Example Research",
            "published_at": "2026-08-02",
        },
    ]
    search_calls = []
    opened = []

    def search(query, max_results):
        search_calls.append((query, max_results))
        return rows

    def read_page(url):
        opened.append(url)
        return {
            "status": 200,
            "title": "Opened title",
            "text": ("Detailed current evidence with irregular   spacing. " * 5),
        }

    result = await ResearchAgent(
        search=search,
        read_page=read_page,
        now=lambda: "2026-08-11T11:22:33+00:00",
    ).run("Gemini Live")

    assert search_calls == [("Gemini Live", 6)]
    assert set(opened) == {row["url"] for row in rows}
    assert result.status == "completed"
    assert result.confidence == "high"
    assert [item.publisher for item in result.evidence] == ["Google AI", "Example Research"]
    assert [item.published_at for item in result.evidence] == ["2026-08-01", "2026-08-02"]
    assert {item.retrieved_at for item in result.evidence} == {"2026-08-11T11:22:33+00:00"}
    assert {item.confidence for item in result.evidence} == {"high"}
    assert "  " not in result.evidence[0].excerpt_summary
    assert result.evidence[0].excerpt_summary.startswith("Detailed current evidence")


@pytest.mark.asyncio
async def test_research_keeps_fallback_when_one_page_open_fails():
    rows = [
        {"title": "Good", "url": "https://good.example/a", "snippet": "good", "publisher": "Good"},
        {"title": "Fallback", "url": "https://fallback.example/b", "snippet": "Search result fallback", "publisher": "Fallback"},
    ]

    def read_page(url):
        if "fallback" in url:
            raise RuntimeError("transient fetch failure")
        return {"status": 200, "text": "Useful source text. " * 10}

    result = await ResearchAgent(search=lambda query, max_results: rows, read_page=read_page).run("query")

    assert result.status == "completed"
    assert result.confidence == "medium"
    assert [item.confidence for item in result.evidence] == ["high", "low"]
    assert result.evidence[1].excerpt_summary == "Search result fallback"


@pytest.mark.asyncio
async def test_research_reports_low_confidence_when_no_page_can_be_opened():
    row = {"title": "Result", "url": "https://example.com/a", "snippet": "Search-only snippet"}
    result = await ResearchAgent(
        search=lambda query, max_results: [row],
        read_page=lambda url: {"status": 503, "text": "unavailable"},
    ).run("query")

    assert result.status == "partial"
    assert result.confidence == "low"
    assert result.evidence[0].confidence == "low"
    assert result.evidence[0].excerpt_summary == "Search-only snippet"


@pytest.mark.asyncio
async def test_research_search_failure_and_empty_results_are_failed_without_fabrication():
    failed = await ResearchAgent(
        search=lambda query, max_results: (_ for _ in ()).throw(RuntimeError("search outage")),
        read_page=lambda url: {},
    ).run("query")
    empty = await ResearchAgent(search=lambda query, max_results: [], read_page=lambda url: {}).run("query")

    for result in (failed, empty):
        assert result.status == "failed"
        assert result.confidence == "low"
        assert result.evidence == []
        assert result.suggested_next_action


@pytest.mark.asyncio
async def test_research_never_fetches_private_literal_targets():
    rows = [
        {"title": "loopback", "url": "http://127.0.0.1/private", "snippet": "private"},
        {"title": "rfc1918", "url": "http://10.0.0.4/private", "snippet": "private"},
        {"title": "link local", "url": "http://169.254.169.254/latest/meta-data", "snippet": "private"},
        {"title": "reserved", "url": "http://240.0.0.1/private", "snippet": "private"},
        {"title": "public", "url": "https://example.com/public", "snippet": "public"},
    ]
    opened = []

    def read_page(url):
        opened.append(url)
        return {"status": 200, "text": "Public evidence. " * 10}

    result = await ResearchAgent(search=lambda query, max_results: rows, read_page=read_page).run("query")

    assert opened == ["https://example.com/public"]
    assert [item.url for item in result.evidence] == ["https://example.com/public"]


@pytest.mark.asyncio
async def test_research_default_reader_uses_and_closes_one_browser_per_page(monkeypatch):
    instances = []

    class FakeBrowser:
        def __init__(self):
            self.closed = False
            instances.append(self)

        def fetch_page(self, url):
            return {"status": 200, "text": "Fetched public source content. " * 6}

        def close(self):
            self.closed = True

    monkeypatch.setattr("app.services.agents.research.WebBrowser", FakeBrowser)
    rows = [
        {"title": "One", "url": "https://one.example/a", "publisher": "One"},
        {"title": "Two", "url": "https://two.example/b", "publisher": "Two"},
    ]

    result = await ResearchAgent(search=lambda query, max_results: rows).run("query")

    assert result.confidence == "high"
    assert len(instances) == 2
    assert all(instance.closed for instance in instances)


@pytest.mark.asyncio
async def test_recovery_never_exceeds_strict_retry_limit():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("temporary outage")

    recovery = RecoveryAgent()
    result = await recovery.run_read_only(operation, retry_limit=2)

    assert attempts == 2
    assert recovery.last_attempts == 2
    assert result.status == "failed"
    assert result.evidence == []
    assert result.suggested_next_action
    assert "temporary outage" in result.error
    assert "completed" not in result.summary.lower()


@pytest.mark.asyncio
async def test_recovery_succeeds_after_transient_failed_agent_result():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return AgentResult(status="failed", summary="First attempt failed", error="transient")
        return AgentResult(status="completed", summary="Recovered", evidence=[source()], confidence="high")

    recovery = RecoveryAgent()
    result = await recovery.run_read_only(operation, retry_limit=2)

    assert attempts == 2
    assert recovery.last_attempts == 2
    assert result.status == "completed"
    assert result.summary == "Recovered"


@pytest.mark.asyncio
async def test_recovery_does_not_retry_non_agent_results():
    attempts = 0

    def operation():
        nonlocal attempts
        attempts += 1
        return {"status": "failed"}

    result = await RecoveryAgent().run_read_only(operation, retry_limit=2)

    assert attempts == 1
    assert result.status == "failed"
    assert "AgentResult" in result.error


def test_verifier_retains_unique_valid_http_evidence_and_rejects_invalid_duplicates():
    valid = source()
    result = AgentResult(
        status="completed",
        summary="Research",
        evidence=[
            valid,
            source(),
            source(url="ftp://example.com/file"),
            source(url="https:///missing-host"),
            source(url="https://example.com/not safe"),
        ],
        confidence="high",
    )

    verified = VerifierAgent().verify_research(result)

    assert verified.status == "completed"
    assert verified.evidence == [valid]


def test_verifier_downgrades_completed_without_valid_evidence_and_preserves_low_confidence():
    result = AgentResult(
        status="completed",
        summary="Unsupported current claim",
        evidence=[source(url="not a url", confidence="low")],
        confidence="low",
    )

    verified = VerifierAgent().verify_research(result)

    assert verified.status == "partial"
    assert verified.evidence == []
    assert verified.confidence == "low"
    assert "verify" in verified.suggested_next_action.lower()


@pytest.mark.asyncio
async def test_orchestrator_explicitly_marks_research_unavailable_without_evidence():
    result = AgentResult(
        status="failed",
        summary="Search was unavailable.",
        confidence="low",
        suggested_next_action="Try again later.",
        error="outage",
    )

    prepared = await AgentOrchestrator(research=FakeResearch(result)).prepare("latest Gemini behavior")

    assert prepared.agent_kind == "research"
    assert "Research is unavailable" in prepared.context
    assert "Do not invent current facts or citations" in prepared.context
    assert "Try again later." in prepared.context


@pytest.mark.asyncio
async def test_orchestrator_persists_completed_verified_run_with_actual_attempt(client, exchange):
    headers = exchange("orchestrator@example.com")
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    research = FakeResearch(
        AgentResult(status="completed", summary="Current behavior found.", evidence=[source()], confidence="high")
    )

    with client.app.state.SessionLocal() as db:
        prepared = await AgentOrchestrator(research=research).prepare(
            "latest Gemini Live behavior",
            db=db,
            user_id=user_id,
        )
        run_id = prepared.run_id

    with client.app.state.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        steps = (
            db.query(AgentRunStep)
            .filter(AgentRunStep.run_id == run_id)
            .order_by(AgentRunStep.sequence)
            .all()
        )

    assert run.status == "completed"
    assert json.loads(run.input_json) == {"query": "latest Gemini Live behavior"}
    assert json.loads(run.output_json)["evidence"][0]["url"] == "https://docs.example.com/live"
    assert [(step.name, step.status) for step in steps] == [
        ("search", "running"),
        ("research", "completed"),
        ("verify", "completed"),
    ]
    assert steps[1].attempt == 1
    assert json.loads(steps[1].evidence_json)[0]["url"] == "https://docs.example.com/live"


@pytest.mark.asyncio
async def test_orchestrator_persists_failed_run_after_bounded_recovery(client, exchange):
    headers = exchange("orchestrator-failure@example.com")
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    research = FakeResearch(
        AgentResult(
            status="failed",
            summary="Search unavailable.",
            confidence="low",
            suggested_next_action="Retry later.",
            error="outage",
        )
    )

    with client.app.state.SessionLocal() as db:
        prepared = await AgentOrchestrator(research=research).prepare(
            "latest Gemini Live behavior",
            db=db,
            user_id=user_id,
        )
        run_id = prepared.run_id

    with client.app.state.SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        steps = db.query(AgentRunStep).filter(AgentRunStep.run_id == run_id).order_by(AgentRunStep.sequence).all()

    assert len(research.queries) == 2
    assert run.status == "failed"
    assert run.error
    assert steps[1].attempt == 2
    assert prepared.result.status == "failed"
