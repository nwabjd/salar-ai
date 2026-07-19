def test_device_registration_and_safe_command_lifecycle(client, auth_headers):
    registered = client.post(
        "/api/devices", headers=auth_headers, json={"name": "Studio PC", "platform": "windows"}
    )
    assert registered.status_code == 201
    device = registered.json()
    assert device["token"]

    queued = client.post(
        "/api/commands",
        headers=auth_headers,
        json={"device_id": device["id"], "kind": "open_url", "payload": {"url": "https://example.com"}},
    )
    assert queued.status_code == 201
    assert queued.json()["status"] == "queued"
    assert queued.json()["requires_confirmation"] is False

    completed = client.post(
        f"/api/device/commands/{queued.json()['id']}/result",
        headers={"X-Device-Token": device["token"]},
        json={"ok": True, "detail": "opened"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_sensitive_command_requires_confirmation(client, auth_headers):
    device = client.post(
        "/api/devices", headers=auth_headers, json={"name": "PC", "platform": "windows"}
    ).json()
    command = client.post(
        "/api/commands",
        headers=auth_headers,
        json={"device_id": device["id"], "kind": "create_directory", "payload": {"path": "C:\\Work\\New"}},
    ).json()
    assert command["status"] == "awaiting_confirmation"
    assert command["requires_confirmation"] is True

    approved = client.post(f"/api/commands/{command['id']}/approve", headers=auth_headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "queued"


def test_unknown_command_is_rejected(client, auth_headers):
    device = client.post(
        "/api/devices", headers=auth_headers, json={"name": "PC", "platform": "windows"}
    ).json()
    response = client.post(
        "/api/commands",
        headers=auth_headers,
        json={"device_id": device["id"], "kind": "run_any_shell", "payload": {"command": "whoami"}},
    )
    assert response.status_code == 422
