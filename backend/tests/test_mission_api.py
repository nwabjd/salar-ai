# tests/test_mission_api.py
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.database import Base, create_session_factory
from app.main import create_app
from app.models import User
from app.security import hash_password
from app.services.missions.runner import MissionRunner


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
async def client(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'api_test.db'}")
    Base.metadata.create_all(engine)
    settings = type("S", (), {
        "database_url": f"sqlite:///{tmp_path / 'api_test.db'}",
        "environment": "test",
        "jwt_secret": "test-secret",
        "token_minutes": 60,
        "bootstrap_email": "test@test.local",
        "bootstrap_password": "pass",
        "allowed_origins": ["*"],
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
    })()
    app = create_app(settings)
    app.state.SessionLocal = sf

    with sf() as db:
        user = User(email="mission@test.local", password_hash=hash_password("pass"))
        db.add(user)
        db.commit()
        user_id = user.id

    from app.security import get_current_user

    async def override_user():
        with sf() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_current_user] = override_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, sf, user_id

    engine.dispose()


@pytest.mark.anyio
async def test_launch_and_get(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    c._transport.app.state.mission_runner = runner

    resp = await c.post("/api/missions", json={"goal": "organize downloads"})
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body["goal"] == "organize downloads"
    assert body["status"] == "queued"

    resp2 = await c.get("/api/missions")
    assert resp2.status_code == 200
    missions = resp2.json()
    assert len(missions) >= 1
    assert any(m["id"] == body["id"] for m in missions)


@pytest.mark.anyio
async def test_cancel(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    c._transport.app.state.mission_runner = runner

    resp = await c.post("/api/missions", json={"goal": "to cancel"})
    body = resp.json()
    resp2 = await c.post(f"/api/missions/{body['id']}/cancel")
    assert resp2.status_code == 200


@pytest.mark.anyio
async def test_404_unowned_mission(client):
    c, sf, user_id = client
    fake_gemini = AsyncMock()
    fake_gemini.chat = AsyncMock(return_value='{"steps": []}')
    runner = MissionRunner(session_factory=sf, gemini=fake_gemini, execute_tool_fn=AsyncMock())
    c._transport.app.state.mission_runner = runner

    with sf() as db:
        other = User(email="other@test.local", password_hash=hash_password("pass"))
        db.add(other)
        db.commit()
        other_id = other.id

    await runner.launch(other_id, "someone else's mission")
    with sf() as db:
        from app.models import Mission
        other_mission = db.scalars(
            __import__("sqlalchemy").select(Mission).where(Mission.user_id == other_id)
        ).first()

    resp = await c.get(f"/api/missions/{other_mission.id}")
    assert resp.status_code == 404
