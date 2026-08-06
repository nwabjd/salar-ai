def test_supabase_exchange_creates_user(client, supabase_token):
    response = client.post("/api/auth/supabase", json={"token": supabase_token(email="newbie@example.com")})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "newbie@example.com"
    assert profile.json()["is_admin"] is False


def test_supabase_exchange_is_idempotent_for_existing_user(client, supabase_token):
    token = supabase_token(email="repeat@example.com")
    first = client.post("/api/auth/supabase", json={"token": token})
    second = client.post("/api/auth/supabase", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["access_token"]
    assert second.json()["access_token"]


def test_supabase_exchange_rejects_invalid_token(client):
    response = client.post("/api/auth/supabase", json={"token": "garbage-not-a-jwt"})

    assert response.status_code == 401


def test_supabase_exchange_rejects_expired_token(client, supabase_token):
    response = client.post("/api/auth/supabase", json={"token": supabase_token(email="late@example.com", expires_in=-60)})

    assert response.status_code == 401


def test_first_login_admin_from_admin_emails(client, supabase_token):
    response = client.post("/api/auth/supabase", json={"token": supabase_token(email="admin@example.com")})

    assert response.status_code == 200
    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "admin@example.com"
    assert profile.json()["is_admin"] is True


def test_profile_requires_bearer_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
