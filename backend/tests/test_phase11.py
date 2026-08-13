# tests/test_phase11.py
import pytest

from app.database import Base, create_session_factory
from app.models import Plugin, User
from app.services.plugins import COMMAND_REGISTRY, PluginError, PluginManager, register_command


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p11.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


MANIFEST = {
    "name": "greeter",
    "version": "1.0.0",
    "description": "Say hello",
    "author": "test",
    "commands": [{"name": "hello", "description": "Say hello"}],
}


def test_install_plugin(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        p = pm.install("u1", MANIFEST)
        db.commit()
        assert p.name == "greeter"
        assert p.enabled is True
    engine.dispose()


def test_install_requires_name(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        with pytest.raises(PluginError):
            PluginManager(db).install("u1", {"version": "1.0"})
    engine.dispose()


def test_install_updates_existing(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        p1 = pm.install("u1", MANIFEST)
        p2 = pm.install("u1", {**MANIFEST, "version": "2.0.0"})
        db.commit()
        assert p1.id == p2.id
        assert p2.version == "2.0.0"
    engine.dispose()


def test_list_toggle_uninstall(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        pm.install("u1", MANIFEST)
        db.commit()
        plugin = pm.list("u1")[0]
        toggled = pm.toggle("u1", plugin["id"], False)
        db.commit()
        assert toggled["enabled"] is False
        assert pm.uninstall("u1", plugin["id"]) is True
        db.commit()
        assert pm.list("u1") == []
    engine.dispose()


def test_execute_registered_command(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        @register_command("greeter", "hello")
        def hello(db, args):
            return {"status": "ok", "greeting": f"Hello, {args.get('name', 'world')}!"}

        pm = PluginManager(db)
        pm.install("u1", MANIFEST)
        db.commit()
        result = pm.execute("u1", "greeter", "hello", {"name": "SALAR"})
        assert result["greeting"] == "Hello, SALAR!"
    engine.dispose()


def test_execute_not_registered(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        pm.install("u1", MANIFEST)
        db.commit()
        with pytest.raises(PluginError):
            pm.execute("u1", "greeter", "missing_command")
    engine.dispose()


def test_execute_disabled_plugin(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        p = pm.install("u1", MANIFEST)
        pm.toggle("u1", p.id, False)
        db.commit()
        with pytest.raises(PluginError):
            pm.execute("u1", "greeter", "hello")
    engine.dispose()


def test_commands_visible_when_enabled(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        pm = PluginManager(db)
        pm.install("u1", MANIFEST)
        db.commit()
        commands = pm.commands("u1")
        assert any(c["name"] == "hello" for c in commands)
    engine.dispose()


def test_marketplace_has_plugins(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        mp = PluginManager(db).marketplace()
        assert any(p["name"] == "translator" for p in mp)
    engine.dispose()


def test_plugin_model(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        db.add(Plugin(id="pl1", user_id="u1", name="x"))
        db.commit()
        assert db.get(Plugin, "pl1").enabled is True
    engine.dispose()
