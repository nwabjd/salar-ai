# tests/test_core_bus.py
import pytest

from app.database import Base, create_session_factory
from app.models import CoreEventLog, User
from app.services.core.events import CoreBus, CoreEvent, TASK_STARTED, TOOL_CALLED, VERIFICATION_PASSED


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'bus.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


@pytest.mark.asyncio
async def test_publish_dispatches_to_subscriber(tmp_path):
    engine, sf = _env(tmp_path)
    bus = CoreBus(db_factory=sf)
    seen = []

    async def handler(event):
        seen.append(event.type)

    bus.subscribe(TOOL_CALLED, handler)
    await bus.publish(CoreEvent(type=TOOL_CALLED, payload={"tool": "file_read"}, trace_id="tr1"))
    assert seen == [TOOL_CALLED]
    engine.dispose()


@pytest.mark.asyncio
async def test_handler_error_does_not_break_bus(tmp_path):
    engine, sf = _env(tmp_path)
    bus = CoreBus(db_factory=sf)
    seen = []

    async def bad_handler(event):
        raise RuntimeError("boom")

    def good_handler(event):
        seen.append(event.type)

    bus.subscribe(TASK_STARTED, bad_handler)
    bus.subscribe(TASK_STARTED, good_handler)
    await bus.publish(CoreEvent(type=TASK_STARTED, trace_id="tr1"))
    assert seen == [TASK_STARTED]
    engine.dispose()


@pytest.mark.asyncio
async def test_journal_persists_events(tmp_path):
    engine, sf = _env(tmp_path)
    bus = CoreBus(db_factory=sf)
    await bus.publish(CoreEvent(type=VERIFICATION_PASSED, payload={"ok": True}, trace_id="tr1"))
    with sf() as db:
        rows = db.query(CoreEventLog).all()
        assert len(rows) == 1
        assert rows[0].event_type == VERIFICATION_PASSED
        assert rows[0].trace_id == "tr1"
    engine.dispose()


@pytest.mark.asyncio
async def test_history_replays_in_order(tmp_path):
    engine, sf = _env(tmp_path)
    bus = CoreBus(db_factory=sf)
    await bus.publish(CoreEvent(type=TASK_STARTED, trace_id="tr9"))
    await bus.publish(CoreEvent(type=TOOL_CALLED, trace_id="tr9"))
    await bus.publish(CoreEvent(type=VERIFICATION_PASSED, trace_id="tr9"))
    events = bus.history("tr9")
    assert [e.type for e in events] == [TASK_STARTED, TOOL_CALLED, VERIFICATION_PASSED]
    engine.dispose()


@pytest.mark.asyncio
async def test_publish_without_db_factory_does_not_journal(tmp_path):
    bus = CoreBus(db_factory=None)
    await bus.publish(CoreEvent(type=TASK_STARTED, trace_id="tr1"))
    assert bus.history("tr1") == []
