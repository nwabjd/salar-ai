from sqlalchemy import text


def provision(client, name="Studio PC"):
    return client.post(
        "/api/auth/desktop/provision",
        json={"provisioning_key": "test-provisioning-key", "name": name},
    )


def test_desktop_provisioning_returns_hashed_device_session(client):
    response = provision(client)
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"].startswith("sds_")
    assert body["device"]["name"] == "Studio PC"

    with client.app.state.SessionLocal() as db:
        token_hash = db.execute(text("select token_hash from device_sessions limit 1")).scalar_one()
        assert token_hash != body["access_token"]


def test_wrong_provisioning_key_is_rejected(client):
    response = client.post(
        "/api/auth/desktop/provision",
        json={"provisioning_key": "wrong", "name": "Unknown PC"},
    )
    assert response.status_code == 401


def test_device_session_authenticates_existing_api(client):
    token = provision(client).json()["access_token"]
    response = client.get("/api/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_pairing_code_is_single_use(client):
    token = provision(client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/auth/pairing", headers=headers)
    assert created.status_code == 201
    code = created.json()["code"]
    assert len(code) == 6 and code.isdigit()

    first = client.post(
        "/api/auth/pairing/redeem",
        json={"code": code, "name": "JD iPhone", "platform": "ios"},
    )
    replay = client.post(
        "/api/auth/pairing/redeem",
        json={"code": code, "name": "Replay", "platform": "web"},
    )
    assert first.status_code == 201
    assert first.json()["access_token"].startswith("sds_")
    assert replay.status_code == 409


def test_expired_pairing_code_is_rejected(client):
    client.app.state.settings.pairing_code_minutes = -1
    token = provision(client).json()["access_token"]
    created = client.post("/api/auth/pairing", headers={"Authorization": f"Bearer {token}"}).json()
    response = client.post(
        "/api/auth/pairing/redeem",
        json={"code": created["code"], "name": "Late browser", "platform": "web"},
    )
    assert response.status_code == 410


def test_revoked_device_session_is_rejected(client):
    provisioned = provision(client).json()
    headers = {"Authorization": f"Bearer {provisioned['access_token']}"}
    response = client.delete(f"/api/auth/devices/{provisioned['device']['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/api/auth/session", headers=headers).status_code == 401
