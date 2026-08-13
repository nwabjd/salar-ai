from datetime import datetime, timedelta, timezone

from app.models import Reminder, Task
from app.services.intel.briefing import build_email_triage, build_morning_brief
from app.services.intel.events import IntelEventStore


def _due(days_from_now: int) -> datetime:
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    return now + timedelta(days=days_from_now)


def test_morning_brief_rolls_up_events_tasks_reminders(client, exchange):
    headers = exchange("brief@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        store.record(user_id=me["id"], kind="email_bill", severity="warning", title="ACME invoice", source="email")
        db.commit()
    with client.app.state.SessionLocal() as db:
        IntelEventStore(db).record(user_id=me["id"], kind="brief", severity="info", title="morning brief", source="briefing")
        db.commit()
    with client.app.state.SessionLocal() as db:
        db.add(Task(user_id=me["id"], title="Overdue tax filing", status="todo", due_date=_due(-1)))
        db.add(Task(user_id=me["id"], title="Ship report", status="in_progress", due_date=_due(0)))
        db.add(Reminder(user_id=me["id"], title="Call the accountant", is_done=False, remind_at=_due(0)))
        db.commit()

        brief = build_morning_brief(db, me["id"])
        assert brief["unread_count"] == 2
        assert [e["kind"] for e in brief["events"]] == ["brief", "email_bill"]
        assert [t["title"] for t in brief["tasks"]["overdue"]] == ["Overdue tax filing"]
        assert [t["title"] for t in brief["tasks"]["today"]] == ["Ship report"]
        assert [r["title"] for r in brief["reminders"]["today"]] == ["Call the accountant"]


def test_morning_brief_excludes_completed_and_distant_tasks(client, exchange):
    headers = exchange("brief-empty@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        db.add(Task(user_id=me["id"], title="Done", status="completed", due_date=_due(0)))
        db.add(Task(user_id=me["id"], title="Next month", status="todo", due_date=_due(30)))
        db.commit()

        brief = build_morning_brief(db, me["id"])
        assert brief["tasks"]["overdue"] == []
        assert brief["tasks"]["today"] == []
        assert brief["unread_count"] == 0


def test_email_triage_returns_email_kinds_only(client, exchange):
    headers = exchange("triage@example.com")
    me = client.get("/api/auth/me", headers=headers).json()

    with client.app.state.SessionLocal() as db:
        store = IntelEventStore(db)
        store.record(user_id=me["id"], kind="email_bill", severity="warning", title="bill")
        store.record(user_id=me["id"], kind="email_action", severity="warning", title="action")
        store.record(user_id=me["id"], kind="brief", severity="info", title="brief")
        db.commit()

        triage = build_email_triage(db, me["id"])
        assert triage["unread_count"] == 3
        assert {e["kind"] for e in triage["email_events"]} == {"email_action", "email_bill"}
