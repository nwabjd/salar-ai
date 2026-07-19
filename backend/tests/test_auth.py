def test_bootstrap_owner_can_login_and_read_profile(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "OWNER@example.com", "password": "CorrectHorseBatteryStaple!"},
    )

    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "owner@example.com"
    assert profile.json()["is_admin"] is True


def test_invalid_password_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_profile_requires_bearer_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
