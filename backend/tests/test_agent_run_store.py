import json

from app.models import AgentRun, AgentRunStep, User
from app.services.agents.run_store import AgentRunStore


def test_agent_run_store_persists_completed_research_run(client, exchange):
    headers = exchange("researcher@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        user = db.get(User, me["id"])
        store = AgentRunStore(db)
        run = store.start(
            user_id=user.id,
            conversation_id=None,
            kind="research",
            input_data={"query": "Gemini Live API"},
        )
        store.step(run, "search", "running", detail={"query": "Gemini Live API"})
        store.step(
            run,
            "search",
            "completed",
            detail={"result_count": 1},
            evidence=(
                {
                    "title": "Gemini Live API",
                    "url": "https://ai.google.dev/api/live",
                    "excerpt_summary": "Live API documentation",
                }
                for _ in range(1)
            ),
        )
        store.complete(run, {"summary": "Gemini Live API supports realtime interaction."})
        db.commit()

        db.expire_all()
        saved_run = db.get(AgentRun, run.id)
        saved_steps = (
            db.query(AgentRunStep)
            .filter(AgentRunStep.run_id == run.id)
            .order_by(AgentRunStep.created_at, AgentRunStep.id)
            .all()
        )

    assert saved_run.status == "completed"
    assert json.loads(saved_run.input_json) == {"query": "Gemini Live API"}
    assert json.loads(saved_run.output_json) == {"summary": "Gemini Live API supports realtime interaction."}
    assert [(step.name, step.status) for step in saved_steps] == [
        ("search", "running"),
        ("search", "completed"),
    ]
    assert json.loads(saved_steps[1].evidence_json)[0]["url"] == "https://ai.google.dev/api/live"
