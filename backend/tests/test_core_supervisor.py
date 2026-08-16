# tests/test_core_supervisor.py
import pytest

from app.services.core.events import (
    AGENT_FINISHED,
    CoreBus,
    CoreEvent,
    SUPERVISOR_ALERT,
    TOOL_CALLED,
    TOOL_RESULT,
    VERIFICATION_FAILED,
)
from app.services.core.supervisor import Supervisor


def _ev(event_type, payload=None, trace_id="tr1"):
    return CoreEvent(type=event_type, payload=payload or {}, trace_id=trace_id)


@pytest.mark.asyncio
async def test_loop_rule_fires_on_repeated_tool_call():
    sup = Supervisor()
    tool = {"tool": "run_command", "args": {"command": "mkdir -p /x"}}
    assert await sup.watch(_ev(TOOL_CALLED, tool)) is None
    assert await sup.watch(_ev(TOOL_CALLED, tool)) is None
    alert = await sup.watch(_ev(TOOL_CALLED, tool))
    assert alert is not None and alert.rule == "loop"
    assert alert.severity == "warning"


@pytest.mark.asyncio
async def test_failure_cascade_rule_fires():
    sup = Supervisor()
    assert await sup.watch(_ev(VERIFICATION_FAILED, {"step": "s1"})) is None
    alert = await sup.watch(_ev(VERIFICATION_FAILED, {"step": "s2"}))
    assert alert is not None and alert.rule == "failure_cascade"


@pytest.mark.asyncio
async def test_conflict_rule_fires_on_dissimilar_low_confidence():
    sup = Supervisor()
    await sup.watch(_ev(AGENT_FINISHED, {"kind": "A", "result": "the sky is blue and the sun is bright", "confidence": 0.6}))
    alert = await sup.watch(_ev(AGENT_FINISHED, {"kind": "B", "result": "elephants are heavy animals living in forests", "confidence": 0.5}))
    assert alert is not None and alert.rule == "conflict"


@pytest.mark.asyncio
async def test_conflict_rule_silent_on_similar_content():
    sup = Supervisor()
    await sup.watch(_ev(AGENT_FINISHED, {"kind": "A", "result": "the sky is blue today", "confidence": 0.9}))
    assert await sup.watch(_ev(AGENT_FINISHED, {"kind": "B", "result": "the sky is blue today indeed", "confidence": 0.9})) is None


@pytest.mark.asyncio
async def test_token_spike_rule_fires_on_large_results():
    sup = Supervisor()
    big = {"tool": "file_read", "result": {"content": "x" * (50 * 1024)}}
    await sup.watch(_ev(TOOL_RESULT, big))
    await sup.watch(_ev(TOOL_RESULT, big))
    alert = await sup.watch(_ev(TOOL_RESULT, big))
    assert alert is not None and alert.rule == "token_spike"


@pytest.mark.asyncio
async def test_dangerous_action_rule_fires_without_approval():
    sup = Supervisor()
    alert = await sup.watch(_ev(TOOL_CALLED, {"tool": "code_run", "args": {"code": "rm -rf"}}))
    assert alert is not None and alert.rule == "dangerous_action"
    assert alert.severity == "critical"


@pytest.mark.asyncio
async def test_dangerous_action_silent_after_approval():
    sup = Supervisor()
    await sup.watch(_ev("TASK_APPROVED"))
    assert await sup.watch(_ev(TOOL_CALLED, {"tool": "code_run", "args": {"code": "rm -rf"}})) is None


@pytest.mark.asyncio
async def test_clean_stream_raises_no_alerts():
    sup = Supervisor()
    await sup.watch(_ev(TOOL_CALLED, {"tool": "file_read", "args": {"path": "/a"}}))
    await sup.watch(_ev(TOOL_RESULT, {"tool": "file_read", "result": {"content": "short"}}))
    await sup.watch(_ev(VERIFICATION_FAILED, {"step": "s1"}))
    await sup.watch(_ev(AGENT_FINISHED, {"kind": "A", "result": "same result content", "confidence": 0.9}))
    await sup.watch(_ev(AGENT_FINISHED, {"kind": "B", "result": "same result content", "confidence": 0.9}))
    assert sup.alerts == []


@pytest.mark.asyncio
async def test_watch_publishes_supervisor_alert_to_bus():
    bus = CoreBus(db_factory=None)
    published = []
    bus.subscribe(SUPERVISOR_ALERT, lambda e: published.append(e))
    sup = Supervisor(bus=bus)
    await sup.watch(_ev(TOOL_CALLED, {"tool": "code_run", "args": {"code": "rm -rf"}}))
    assert any(e.type == SUPERVISOR_ALERT for e in published)
    assert bus.published_count == 1


@pytest.mark.asyncio
async def test_subscribe_to_wires_handlers():
    bus = CoreBus(db_factory=None)
    sup = Supervisor()
    sup.subscribe_to(bus)
    await bus.publish(_ev(TOOL_CALLED, {"tool": "code_run", "args": {"code": "x"}}))
    assert len(sup.alerts) == 1
    assert sup.alerts[0].rule == "dangerous_action"


@pytest.mark.asyncio
async def test_alert_fires_once_per_trace():
    sup = Supervisor()
    tool = {"tool": "run_command", "args": {"command": "mkdir -p /x"}}
    await sup.watch(_ev(TOOL_CALLED, tool))
    await sup.watch(_ev(TOOL_CALLED, tool))
    await sup.watch(_ev(TOOL_CALLED, tool))
    await sup.watch(_ev(TOOL_CALLED, tool))
    assert len(sup.alerts) == 1
