# tests/test_core_verification.py
import pytest

from app.services.core.toolspec import ToolSpec
from app.services.core.verification import VerificationEngine, VerifierResult


def _spec(verification="auto"):
    return ToolSpec(name="t", description="", risk_level=1, permission_category="safe", verification=verification)


@pytest.mark.asyncio
async def test_file_write_passes_when_content_matches(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("hello")
    args = {"path": str(target), "content": "hello"}
    result = {"path": str(target), "ok": True}
    r = await VerificationEngine().verify(_spec("file_write"), args, result, {})
    assert r.passed is True
    assert r.confidence >= 0.99


@pytest.mark.asyncio
async def test_file_write_fails_when_content_differs(tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("other")
    args = {"path": str(target), "content": "hello"}
    result = {"path": str(target)}
    r = await VerificationEngine().verify(_spec("file_write"), args, result, {})
    assert r.passed is False


@pytest.mark.asyncio
async def test_file_read_passes_on_nonempty(tmp_path):
    target = tmp_path / "b.txt"
    target.write_text("data")
    args = {"path": str(target)}
    result = {"path": str(target), "content": "data"}
    r = await VerificationEngine().verify(_spec("file_read"), args, result, {})
    assert r.passed is True


@pytest.mark.asyncio
async def test_list_files_passes(tmp_path):
    r = await VerificationEngine().verify(_spec("list_files"), {"path": str(tmp_path)}, {"files": []}, {})
    assert r.passed is True


@pytest.mark.asyncio
async def test_run_command_exit_code():
    eng = VerificationEngine()
    ok = await eng.verify(_spec("run_command"), {"command": "true"}, {"exit_code": 0}, {})
    bad = await eng.verify(_spec("run_command"), {"command": "false"}, {"exit_code": 1, "stderr": "boom"}, {})
    assert ok.passed is True
    assert bad.passed is False


@pytest.mark.asyncio
async def test_code_run():
    eng = VerificationEngine()
    ok = await eng.verify(_spec("code_run"), {"code": "print(1)"}, {"output": "1", "result": 1}, {})
    bad = await eng.verify(_spec("code_run"), {"code": "x"}, {"error": "NameError"}, {})
    assert ok.passed is True
    assert bad.passed is False


@pytest.mark.asyncio
async def test_open_url_status():
    eng = VerificationEngine()
    ok = await eng.verify(_spec("open_url"), {"url": "x"}, {"status_code": 200}, {})
    bad = await eng.verify(_spec("open_url"), {"url": "x"}, {"status_code": 500}, {})
    assert ok.passed is True
    assert bad.passed is False


@pytest.mark.asyncio
async def test_send_message():
    eng = VerificationEngine()
    ok = await eng.verify(_spec("send_message"), {}, {"ok": True, "id": "m1"}, {})
    bad = await eng.verify(_spec("send_message"), {}, {"ok": False}, {})
    assert ok.passed is True
    assert bad.passed is False


@pytest.mark.asyncio
async def test_auto_default():
    eng = VerificationEngine()
    ok = await eng.verify(_spec("auto"), {}, {"result": "x"}, {})
    empty = await eng.verify(_spec("auto"), {}, None, {})
    errored = await eng.verify(_spec("auto"), {}, {"result": "x"}, {"error": "boom"})
    assert ok.passed is True
    assert empty.passed is False
    assert errored.passed is False


@pytest.mark.asyncio
async def test_none_verifier():
    r = await VerificationEngine().verify(_spec("none"), {}, {"x": 1}, {})
    assert r.passed is True
    assert r.confidence == 0.3


@pytest.mark.asyncio
async def test_unknown_verifier():
    r = await VerificationEngine().verify(_spec("nope"), {}, {"x": 1}, {})
    assert r.passed is False
