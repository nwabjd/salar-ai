from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class FakeCoordinator:
    async def reply(self, *, prompt, messages, memories, documents):
        return f"Test response to: {prompt}"


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
    )
    app = create_app(settings)
    app.state.coordinator = FakeCoordinator()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "CorrectHorseBatteryStaple!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
