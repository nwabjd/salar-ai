import pytest

from app.database import Base, create_session_factory
from app.models import User
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.intel.events import IntelEventStore


@pytest.mark.asyncio
async def test_orchestrator_injects_intel_context_for_non_research_prompts(tmp_path):
    engine, session_factory = create_session_factory(f"sqlite:///{tmp_path / 'intel-orch.db'}")
    Base.metadata.create_all(engine)
    try:
        with session_factory() as db:
            user = User(email="intel-orch@example.com", password_hash="hash")
            db.add(user)
            db.flush()
            user_id = user.id
            IntelEventStore(db).record(
                user_id=user_id, kind="email_bill", severity="warning",
                title="ACME invoice", summary="You owe $49.",
            )
            db.commit()

            orchestrator = AgentOrchestrator()
            prepared = await orchestrator.prepare(
                prompt="Anything important today?",
                db=db,
                user_id=user_id,
                conversation_id=None,
            )
            assert prepared.agent_kind == "none"
            assert "ACME invoice" in prepared.context
            assert "UNTRUSTED_BACKGROUND_INTEL_BEGIN" in prepared.context

            # The intel intent short-circuits even though "today" alone would
            # match the research pattern.
            assert orchestrator.needs_research("Anything important today?") is True
            assert orchestrator.needs_research("what is the latest news about AI?") is True
            assert orchestrator.needs_research("How do I use the API?") is False
    finally:
        engine.dispose()
