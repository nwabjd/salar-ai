from app.services.intel.events import IntelEventStore


def test_intel_api_brief_events_ack_and_jobs(client, exchange):
    headers = exchange("intel-api@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        store.record(user_id=me["id"], kind="email_bill", severity="warning", title="ACME invoice", source="email")
        event_id = store.record(user_id=me["id"], kind="brief", severity="info", title="Morning brief", source="briefing").id
        db.commit()

    # List events.
    response = client.get("/api/intel/events", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["events"]) == 2
    assert {e["kind"] for e in body["events"]} == {"email_bill", "brief"}

    # Unread count.
    assert client.get("/api/intel/unread-count", headers=headers).json()["unread_count"] == 2

    # Ack a single event.
    assert client.post(f"/api/intel/events/{event_id}/ack", headers=headers).status_code == 200
    assert client.get("/api/intel/unread-count", headers=headers).json()["unread_count"] == 1

    # Ack everything.
    assert client.post("/api/intel/ack-all", headers=headers).json()["acked"] == 1
    assert client.get("/api/intel/unread-count", headers=headers).json()["unread_count"] == 0

    # Briefs compose from the ledger.
    brief = client.get("/api/intel/brief?brief_type=morning", headers=headers).json()
    assert brief["generated_at"]
    triage = client.get("/api/intel/brief?brief_type=email", headers=headers).json()
    assert triage["email_events"]

    # Jobs list exists and is empty for this user.
    jobs = client.get("/api/intel/jobs", headers=headers).json()
    assert jobs["jobs"] == []


def test_intel_api_requires_auth(client):
    response = client.get("/api/intel/events")
    assert response.status_code in (401, 403)
