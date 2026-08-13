# tests/test_phase6.py
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.database import Base, create_session_factory
from app.models import IntelEvent, KnowledgeChunk, KnowledgeDocument, Notification, User
from app.services.notifications import NotificationCenter
from app.services.automation import AutomationManager
from app.services.file_assistant import FileAssistant
from app.services.file_organizer import EXTENSION_FOLDERS, FileOrganizer


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p6.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_notification_push_and_list(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        nc = NotificationCenter(db)
        nc.push("u1", "intel", "New bill due")
        nc.push("u1", "alert", "High CPU", severity="warning")
        db.commit()
        items = nc.list("u1")
        assert len(items) == 2
        assert nc.unread_count("u1") == 2
        nc.mark_read("u1", items[0]["id"])
        db.commit()
        assert nc.unread_count("u1") == 1
        assert len(nc.list("u1", unread_only=True)) == 1
    engine.dispose()


def test_notification_mark_all(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        nc = NotificationCenter(db)
        nc.push("u1", "system", "a")
        nc.push("u1", "system", "b")
        db.commit()
        assert nc.mark_all_read("u1") == 2
        db.commit()
        assert nc.unread_count("u1") == 0
    engine.dispose()


def test_automation_routes_intel_to_notification(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        ev = IntelEvent(id="i1", user_id="u1", kind="email_bill", severity="warning", title="ACME invoice", summary="$50 due", seq=1, created_at=datetime.now(timezone.utc))
        db.add(ev)
        db.commit()
        am = AutomationManager(db)
        notification = am.process_intel_event("u1", ev)
        db.commit()
        assert notification is not None
        assert notification.kind == "email"
        assert notification.severity == "warning"
    engine.dispose()


def test_automation_ignores_unknown(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        am = AutomationManager(db)
        assert am.process_intel_event("u1", None) is None
    engine.dispose()


@pytest.mark.asyncio
async def test_file_assistant_uses_context(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(KnowledgeDocument(id="d1", user_id="u1", filename="platforms.txt", storage_path="x"))
        db.flush()
        db.add(KnowledgeChunk(id="c1", document_id="d1", user_id="u1", chunk_index=0, content="SALAR supports Windows, macOS and Linux."))
        db.commit()
        gemini = AsyncMock()
        gemini.chat = AsyncMock(return_value="SALAR supports Windows, macOS and Linux.")
        fa = FileAssistant(db, gemini=gemini)
        result = await fa.ask("u1", "Which platforms does SALAR support?")
        assert result["status"] == "ok"
        assert "Windows" in result["answer"]
    engine.dispose()


@pytest.mark.asyncio
async def test_file_assistant_no_context(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        fa = FileAssistant(db, gemini=None)
        result = await fa.ask("u1", "anything?")
        assert result["source_count"] == 0
    engine.dispose()


def test_organizer_extension_folders():
    assert ".png" in EXTENSION_FOLDERS["images"]
    assert ".py" in EXTENSION_FOLDERS["code"]
    assert ".zip" in EXTENSION_FOLDERS["archives"]


def test_organizer_plan_and_apply(tmp_path):
    root = tmp_path / "organize"
    root.mkdir()
    (root / "photo.png").write_text("x")
    (root / "script.py").write_text("x")
    org = FileOrganizer(root)
    plan = org.plan()
    assert len(plan) == 2
    folders = {p["target_folder"] for p in plan}
    assert {"images", "code"} <= folders
    result = org.apply()
    assert len(result["moved"]) == 2
    assert (root / "images" / "photo.png").exists()
    assert (root / "code" / "script.py").exists()


def test_notification_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Notification(id="n1", user_id="u1", kind="system", title="t"))
        db.commit()
        assert db.get(Notification, "n1").is_read is False
    engine.dispose()
