from app.services.intel.email_watch import classify_email, scan_email_account
from app.services.intel.events import IntelEventStore


class FakeEmailAccount:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def search_emails(self, folder="INBOX", query="ALL", limit=20):
        return [
            {"id": "1", "from": "billing@acme.com", "subject": "Invoice #2041 due", "date": "Mon, 1 Jan 2026"},
            {"id": "2", "from": "friend@gmail.com", "subject": "Lunch next week?", "date": "Mon, 1 Jan 2026"},
            {"id": "3", "from": "legal@example.com", "subject": "Please sign here — NDA", "date": "Mon, 1 Jan 2026"},
        ]

    def read_email(self, msg_id, folder="INBOX"):
        return {"id": msg_id, "from": "x", "subject": "s", "date": "d", "body": ""}


def test_scan_email_account_records_events_and_dedups(client, exchange, monkeypatch):
    headers = exchange("scan@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    monkeypatch.setattr("app.services.intel.email_watch.EmailAccount", FakeEmailAccount)

    cfg = {"address": "me@example.com", "password": "secret"}

    with client.app.state.SessionLocal() as db:
        result = scan_email_account(db, me["id"], cfg)
        assert result["scanned"] == 3
        assert result["new_events"] == 2  # invoice (bill) + NDA (action); lunch is quiet

        kinds = [e.kind for e in IntelEventStore(db).recent(me["id"])]
        assert "email_bill" in kinds
        assert "email_action" in kinds
        assert "email_info" not in kinds

        # Second scan: the same messages are deduplicated.
        result2 = scan_email_account(db, me["id"], cfg)
        assert result2["new_events"] == 0
        assert IntelEventStore(db).unread_count(me["id"]) == 2


def test_classify_email_bills():
    kind, severity = classify_email("Your invoice #2041 from Acme", "billing@acme.com")
    assert kind == "email_bill"
    assert severity == "warning"

    kind, severity = classify_email("Payment received — thank you", "no-reply@stripe.com")
    assert kind == "email_bill"


def test_classify_email_action_required():
    kind, severity = classify_email("Action required: approve the budget", "finance@example.com")
    assert kind == "email_action"

    kind, severity = classify_email("Please sign here — final contract", "legal@example.com")
    assert kind == "email_action"


def test_classify_email_important_sender():
    kind, severity = classify_email("Meeting summary attached", "lawyer@smithlaw.com")
    assert kind == "email_important"
    assert severity == "warning"


def test_classify_email_newsletter_is_quiet():
    kind, severity = classify_email("Your weekly digest is here", "news@example.com")
    assert kind == "email_info"
    assert severity == "info"

    kind, severity = classify_email("Sale! 50% off everything", "promo@shop.com")
    assert kind == "email_info"


def test_classify_email_generic_is_quiet():
    kind, severity = classify_email("Coffee with friends this weekend?", "friend@gmail.com")
    assert kind == "email_info"
    assert severity == "info"


def test_classify_email_body_upsells_subject():
    # Subject alone is quiet; body mentions an amount due -> bill.
    kind, severity = classify_email("Acme statement", "support@acme.com", body="Your payment of $120.00 is due.")
    assert kind == "email_bill"


def test_classify_email_newsletter_beats_important_sender():
    kind, severity = classify_email("Weekly newsletter", "news@lawyer.com")
    assert kind == "email_info"
