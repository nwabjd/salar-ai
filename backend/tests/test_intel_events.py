from app.models import IntelEvent
from app.services.intel.events import IntelEventStore


def test_intel_store_records_and_lists(client, exchange):
    headers = exchange("intel@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        event = store.record(
            user_id=me["id"],
            kind="email_bill",
            severity="warning",
            title="Your Acme invoice is ready",
            summary="You owe $49.00 due on the 1st.",
            source="email",
            detail={"from": "billing@acme.com", "amount": 49.00},
            evidence=[{"message_id": "123", "folder": "INBOX"}],
        )
        event_id = event.id
        db.commit()

        assert store.unread_count(me["id"]) == 1

        events = store.recent(me["id"])
        assert len(events) == 1
        dumped = IntelEventStore.to_dict(events[0])
        assert dumped["kind"] == "email_bill"
        assert dumped["detail"]["amount"] == 49.00
        assert dumped["evidence"][0]["message_id"] == "123"

        assert store.ack(event_id, me["id"])
        db.commit()
        assert store.unread_count(me["id"]) == 0
        assert store.recent(me["id"], unread_only=True) == []


def test_intel_store_ack_respects_ownership(client, exchange):
    owner = exchange("intel-owner@example.com")
    other = exchange("intel-other@example.com")
    me = client.get("/api/auth/me", headers=owner).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        event = store.record(user_id=me["id"], kind="system", severity="info", title="notice")
        db.commit()

        assert not store.ack(event.id, "not-the-owner")
        assert store.ack(event.id, me["id"])
        db.commit()


def test_intel_store_ack_all(client, exchange):
    headers = exchange("intel-all@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        store.record(user_id=me["id"], kind="email_bill", severity="warning", title="a")
        store.record(user_id=me["id"], kind="brief", severity="info", title="b")
        db.commit()
        assert store.unread_count(me["id"]) == 2

        assert store.ack_all(me["id"]) == 2
        db.commit()
        assert store.unread_count(me["id"]) == 0


def test_intel_store_filters_by_kind_severity_and_read(client, exchange):
    headers = exchange("intel-filter@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        store.record(user_id=me["id"], kind="email_bill", severity="warning", title="bill")
        db.commit()
    with client.app.state.SessionLocal() as db:
        IntelEventStore(db).record(user_id=me["id"], kind="brief", severity="info", title="brief")
        db.commit()
    with client.app.state.SessionLocal() as db:
        IntelEventStore(db).record(user_id=me["id"], kind="email_action", severity="warning", title="action")
        db.commit()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        assert [e.kind for e in store.recent(me["id"], kinds=["email_bill", "email_action"])] == ["email_action", "email_bill"]
        assert [e.kind for e in store.recent(me["id"], severity="warning")] == ["email_action", "email_bill"]
        assert [e.kind for e in store.recent(me["id"], kinds=["brief"])] == ["brief"]
