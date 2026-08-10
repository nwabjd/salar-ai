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
    response = client.post("/api/auth/supabase", json={"token": supabase_token(email="nwabjd@gmail.com")})

    assert response.status_code == 200
    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "nwabjd@gmail.com"
    assert profile.json()["is_admin"] is True


def test_only_approved_email_is_admin(client, supabase_token):
    for email in ("admin@example.com", "owner@example.com", "nwabjd+alias@gmail.com"):
        response = client.post("/api/auth/supabase", json={"token": supabase_token(email=email, sub=f"sub-{email}")})
        assert response.status_code == 200
        profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
        assert profile.status_code == 200
        assert profile.json()["is_admin"] is False


def test_existing_user_demoted_when_not_admin_email(client, supabase_token):
    response = client.post("/api/auth/supabase", json={"token": supabase_token(email="admin@example.com")})

    assert response.status_code == 200
    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["is_admin"] is False


def test_profile_requires_bearer_token(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_supabase_exchange_accepts_es256_jwks_token(client, monkeypatch):
    import base64
    import time

    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import ec

    from app import security

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()

    def _b64_32(n):
        return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()

    jwk = {
        "kty": "EC",
        "crv": "P-256",
        "alg": "ES256",
        "use": "sig",
        "kid": "test-kid",
        "x": _b64_32(numbers.x),
        "y": _b64_32(numbers.y),
    }

    class _FakeKey:
        def __init__(self, key, kid):
            self.key = key
            self.kid = kid

    class _FakeJWKClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_signing_key_from_jwt(self, token):
            return _FakeKey(public_key, "test-kid")

    monkeypatch.setattr(security, "PyJWKClient", _FakeJWKClient)

    settings = client.app.state.settings
    token = pyjwt.encode(
        {
            "sub": "33333333-4444-5555-6666-777777777777",
            "email": "es256@example.com",
            "aud": settings.supabase_audience,
            "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-kid"},
    )

    response = client.post("/api/auth/supabase", json={"token": token})

    assert response.status_code == 200
    profile = client.get("/api/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "es256@example.com"
