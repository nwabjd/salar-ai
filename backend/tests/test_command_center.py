# tests/test_command_center.py
from datetime import datetime, timedelta, timezone

from app.database import Base, create_session_factory
from app.models import (
    Document, IntelEvent, Memory, Mission, MissionEvent, Reminder, Task, User,
)
from app.services.thought_stream import ThoughtStream


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'cc.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def _now():
    return datetime.now(timezone.utc)


def _seed(tmp_path):
    engine, sf = _env(tmp_path)
    now = _now()
    with sf() as db:
        db.add(Mission(id="m1", user_id="u1", goal="Launch Aura", status="completed",
                       step_count=3, completed_count=3, created_at=now, updated_at=now))
        db.add(Task(id="t1", user_id="u1", title="Fix bug", status="todo", priority="high",
                    due_date=now - timedelta(days=1)))
        db.add(Task(id="t2", user_id="u1", title="Deploy", status="todo", priority="medium",
                    due_date=now + timedelta(days=3)))
        db.add(Reminder(id="r1", user_id="u1", title="Standup", message="sync",
                        remind_at=now + timedelta(hours=2), is_done=False))
        db.add(IntelEvent(id="i1", user_id="u1", kind="email_bill", severity="critical",
                          title="invoice", summary="owes $50", is_read=False, seq=1, created_at=now))
        db.add(IntelEvent(id="i2", user_id="u1", kind="guardian", severity="warning",
                          title="flag", summary="something", is_read=False, seq=2, created_at=now))
        db.add(Memory(id="mem1", user_id="u1", title="project", content="ideas", updated_at=now))
        db.add(Document(id="d1", user_id="u1", filename="file.txt", media_type="text/plain",
                        storage_path="/x", created_at=now))
        db.commit()
    return engine, sf


def test_dashboard_shape(tmp_path):
    from conftest import FakeAgentOrchestrator, FakeCoordinator
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.models import User
    from app.security import get_current_user
    engine, sf = _seed(tmp_path)
    settings = type("S", (), {
        "database_url": f"sqlite:///{tmp_path / 'cc.db'}",
        "environment": "test",
        "jwt_secret": "test-secret",
        "token_minutes": 60,
        "bootstrap_email": "test@test.local",
        "bootstrap_password": "pass",
        "allowed_origins": ["*"],
        "cors_allow_origin_regex": None,
        "log_level": "INFO",
        "storage_dir": tmp_path / "uploads",
        "gemini_api_key": None,
        "gemini_model": "gemini-3.1-flash-lite",
        "public_api_url": "http://localhost:8000",
        "bridge_url": "http://localhost:3100",
        "stripe_secret_key": None,
        "stripe_webhook_secret": None,
        "stripe_price_pro": None,
        "stripe_price_team": None,
        "paypal_client_id": None,
        "paypal_secret": None,
        "payment_wallet_address": "0x0",
        "free_monthly_quota": 500,
        "pro_monthly_quota": 5000,
        "whatsapp_cs_access_token": None,
        "whatsapp_cs_phone_number_id": None,
        "whatsapp_cs_api_version": "v23.0",
    })()
    app = create_app(settings)
    app.state.SessionLocal = sf
    app.state.coordinator = FakeCoordinator()
    app.state.agent_orchestrator = FakeAgentOrchestrator()

    async def override():
        with sf() as db:
            return db.get(User, "u1")
    app.dependency_overrides[get_current_user] = override

    with TestClient(app) as client:
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        d = resp.json()
        assert "missions" in d
        assert "tasks" in d
        assert "calendar" in d
        assert "email" in d
        assert "guardian" in d
        assert "thought_stream" in d
        assert "memory" in d
        assert "files" in d
        assert d["email"]["unread_count"] >= 1
        assert d["files"]["total_documents"] == 1
        assert d["memory"]["total"] == 1
        assert d["user"]["id"] == "u1"
    engine.dispose()
