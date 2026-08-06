from pathlib import Path

import jwt as pyjwt
import pytest
import time
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeCoordinator:
    async def reply(self, *, prompt, messages, memories, documents):
        return f"Test response to: {prompt}"


def make_supabase_token(settings, email="owner@example.com", sub="11111111-2222-3333-4444-555555555555", expires_in=3600):
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": sub,
            "email": email,
            "aud": settings.supabase_audience,
            "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + expires_in,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'salar-test.db'}",
        jwt_secret="test-secret-that-is-long-enough-for-sha256",
        bootstrap_email="owner@example.com",
        bootstrap_password="CorrectHorseBatteryStaple!",
        allowed_origins=["https://salar.example.com"],
        storage_dir=tmp_path / "uploads",
        environment="test",
        supabase_url="https://test.supabase.co",
        supabase_jwt_secret="test-supabase-secret",
        supabase_audience="authenticated",
        admin_emails=["owner@example.com", "admin@example.com"],
        free_monthly_quota=500,
        pro_monthly_quota=5000,
    )
    app = create_app(settings)
    app.state.coordinator = FakeCoordinator()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def supabase_token(client: TestClient):
    def _mint(email="owner@example.com", sub="11111111-2222-3333-4444-555555555555", expires_in=3600):
        return make_supabase_token(client.app.state.settings, email=email, sub=sub, expires_in=expires_in)

    return _mint


def _exchange(client: TestClient, token: str) -> dict:
    response = client.post("/api/auth/supabase", json={"token": token})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def auth_headers(client: TestClient, supabase_token):
    return _exchange(client, supabase_token())


@pytest.fixture()
def admin_headers(client: TestClient, supabase_token):
    return _exchange(client, supabase_token(email="admin@example.com", sub="22222222-3333-4444-5555-666666666666"))


@pytest.fixture()
def exchange(client: TestClient):
    def _exchange_email(email: str, sub=None) -> dict:
        return _exchange(client, make_supabase_token(client.app.state.settings, email=email, sub=sub or f"sub-{email}"))

    return _exchange_email
