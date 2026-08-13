# tests/test_permissions.py
import pytest

from app.database import Base, create_session_factory
from app.models import User
from app.services.permissions import (
    DEFAULT_LEVEL,
    category_for_tool,
    check_permission,
    is_write_tool,
    valid_level,
)


def _make_env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'perm.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_category_mapping():
    assert category_for_tool("run_command") == "terminal"
    assert category_for_tool("code_run") == "terminal"
    assert category_for_tool("file_write") == "files"
    assert category_for_tool("read_file") == "files"
    assert category_for_tool("email_send") == "email"
    assert category_for_tool("browse_page") == "browser"
    assert category_for_tool("screenshot") == "screen"
    assert category_for_tool("power_control") == "system"
    assert category_for_tool("calendar_today") == "calendar"
    assert category_for_tool("create_task") == "calendar"
    assert category_for_tool("whatsapp_send") == "email"
    assert category_for_tool("unknown_tool_xyz") == "system"


def test_default_level_is_ask():
    assert DEFAULT_LEVEL == "ask"


def test_valid_level():
    assert valid_level("autonomous")
    assert valid_level("ask")
    assert valid_level("suggest")
    assert valid_level("observe")
    assert not valid_level("banana")


def test_is_write_tool():
    assert is_write_tool("file_write")
    assert is_write_tool("email_send")
    assert is_write_tool("run_command")
    assert is_write_tool("power_control")
    assert not is_write_tool("read_file")
    assert not is_write_tool("list_files")
    assert not is_write_tool("calendar_today")
    assert not is_write_tool("browse_page")


def test_check_permission_autonomous():
    from app.services.permissions import PermissionProfile
    p = PermissionProfile()  # defaults to ask
    p.set_level("terminal", "autonomous")
    # autonomous + dangerous tool still needs approval (base danger)
    assert check_permission(p, "run_command", {"command": "rm x"}) == "ask"
    # autonomous + safe tool executes
    assert check_permission(p, "list_files", {}) == "safe"


def test_check_permission_ask_gates_everything():
    from app.services.permissions import PermissionProfile
    p = PermissionProfile()
    p.set_level("terminal", "ask")
    assert check_permission(p, "run_command", {}) == "ask"
    assert check_permission(p, "list_files", {}) == "safe"  # different category, default ask -> not gated below danger


def test_check_permission_suggest_never_executes():
    from app.services.permissions import PermissionProfile
    p = PermissionProfile()
    p.set_level("terminal", "suggest")
    assert check_permission(p, "run_command", {}) == "denied"


def test_check_permission_observe_readonly():
    from app.services.permissions import PermissionProfile
    p = PermissionProfile()
    p.set_level("terminal", "observe")
    assert check_permission(p, "run_command", {}) == "denied"  # write tool
    assert check_permission(p, "list_files", {}) == "safe"  # read tool, different category -> default


def test_profile_persists(tmp_path):
    engine, sf = _make_env(tmp_path)
    from app.services.permissions import PermissionProfile
    p = PermissionProfile(user_id="u1")
    p.set_level("email", "suggest")
    with sf() as db:
        p.save(db)
    with sf() as db:
        loaded = PermissionProfile.for_user(db, "u1")
        assert loaded.level_for("email") == "suggest"
        assert loaded.level_for("files") == "ask"
    engine.dispose()
