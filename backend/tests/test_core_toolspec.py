# tests/test_core_toolspec.py
import asyncio

import pytest

from app.database import Base, create_session_factory
from app.models import User
from app.services.core.toolspec import ToolRegistry, ToolSpec


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'ts.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_known_spec_fields():
    reg = ToolRegistry()
    spec = reg.spec("code_run")
    assert spec.name == "code_run"
    assert spec.risk_level == 3
    assert spec.verification == "code_run"
    assert spec.requires_approval is True
    assert reg.spec("file_read").risk_level == 0
    assert reg.spec("run_command").risk_level == 2


def test_default_fallback_spec():
    reg = ToolRegistry()
    spec = reg.spec("does_not_exist")
    assert spec.risk_level == 2
    assert spec.verification == "auto"
    assert spec.permission_category == "reversible"


def test_requires_approval_threshold():
    reg = ToolRegistry()
    assert reg.requires_approval("code_run") is True
    assert reg.requires_approval("file_read") is False


def test_custom_specs_override():
    custom = {"run_command": ToolSpec(name="run_command", description="h", risk_level=1, permission_category="safe", verification="auto")}
    reg = ToolRegistry(specs=custom)
    assert reg.spec("run_command").risk_level == 1


@pytest.mark.asyncio
async def test_run_delegates_to_execute_tool(tmp_path):
    engine, sf = _env(tmp_path)
    reg = ToolRegistry()
    with sf() as db:
        result = await reg.run("list_files", {"path": str(tmp_path)}, "u1", db_session=db)
        assert isinstance(result, dict)
        assert "error" not in result or result.get("error") is None
    engine.dispose()
