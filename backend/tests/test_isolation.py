"""Tenant isolation tests — per-user files, sandboxes, whatsapp routing, admin RBAC."""


def test_file_roots_are_per_user(client, exchange):
    headers_a = exchange("alice@example.com")
    headers_b = exchange("bob@example.com")

    write = client.post("/api/files/write", headers=headers_a, json={"path": "notes.txt", "content": "hi"})
    assert write.status_code == 200

    listing_b = client.get("/api/files/list", headers=headers_b).json()
    assert listing_b["items"] == []

    listing_a = client.get("/api/files/list", headers=headers_a).json()
    assert [i["name"] for i in listing_a["items"]] == ["notes.txt"]

    me_a = client.get("/api/auth/me", headers=headers_a).json()
    root = client.app.state.settings.storage_dir / "users" / me_a["id"] / "notes.txt"
    assert root.exists()
    assert root.read_text(encoding="utf-8") == "hi"


def test_file_traversal_blocked(client, exchange):
    headers = exchange("carol@example.com")
    response = client.post("/api/files/write", headers=headers, json={"path": "../evil.txt", "content": "x"})
    assert response.status_code in (400, 422)
    root = client.app.state.settings.storage_dir / "users"
    assert not (root.parent / "evil.txt").exists()


def test_code_sandbox_per_user(client, exchange):
    headers_a = exchange("dave@example.com")
    headers_b = exchange("erin@example.com")

    r = client.post(
        "/api/code/execute",
        headers=headers_a,
        json={"code": "print('hello')", "language": "python"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r2 = client.post(
        "/api/code/execute",
        headers=headers_a,
        json={"code": "open('sandbox_file.txt', 'w').write('secret')\nprint('done')", "language": "python"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"

    listing_b = client.get("/api/files/list", headers=headers_b).json()
    assert listing_b["items"] == []

    sandbox_a = client.get("/api/files/list?path=sandbox", headers=headers_a).json()
    assert [i["name"] for i in sandbox_a["items"]] == ["sandbox_file.txt"]


def test_monitor_requires_admin(client, exchange, admin_headers):
    free = exchange("frank@example.com")
    denied = client.get("/api/monitor/snapshot", headers=free)
    assert denied.status_code == 403
    allowed = client.get("/api/monitor/snapshot", headers=admin_headers)
    assert allowed.status_code == 200


def test_alerts_require_admin(client, exchange, admin_headers):
    free = exchange("grace@example.com")
    denied = client.get("/api/alerts/rules", headers=free)
    assert denied.status_code == 403
    allowed = client.get("/api/alerts/rules", headers=admin_headers)
    assert allowed.status_code == 200


def test_whatsapp_route_threads_user(client, exchange):
    class FakeWA:
        def __init__(self):
            self.calls = []

        async def get_status(self, user_id):
            self.calls.append(user_id)
            return {"status": "connected", "user_id": user_id}

    fake = FakeWA()
    client.app.state.whatsapp = fake

    headers = exchange("helen@example.com")
    me = client.get("/api/auth/me", headers=headers).json()
    r = client.get("/api/whatsapp/status", headers=headers)
    assert r.status_code == 200
    assert fake.calls == [me["id"]]
    assert r.json()["user_id"] == me["id"]


def test_whatsapp_contact_state_does_not_cross_users(client, exchange):
    from sqlalchemy import select
    from app.models import WhatsAppContactState

    headers_a = exchange("contact-owner-a@example.com")
    headers_b = exchange("contact-owner-b@example.com")
    user_a = client.get("/api/auth/me", headers=headers_a).json()
    user_b = client.get("/api/auth/me", headers=headers_b).json()

    with client.app.state.SessionLocal() as db:
        db.add_all([
            WhatsAppContactState(user_id=user_a["id"], contact_jid="same@s.whatsapp.net", introduced=True),
            WhatsAppContactState(user_id=user_b["id"], contact_jid="same@s.whatsapp.net", introduced=False),
        ])
        db.commit()
        rows = list(db.scalars(select(WhatsAppContactState).where(
            WhatsAppContactState.contact_jid == "same@s.whatsapp.net"
        )))

    assert {(row.user_id, row.introduced) for row in rows} == {
        (user_a["id"], True),
        (user_b["id"], False),
    }
