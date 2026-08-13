# tests/test_phase7.py
from app.database import Base, create_session_factory
from app.models import User
from app.services.system.app_launcher import AppLauncher
from app.services.system.media_controller import MediaController, VALID_ACTIONS
from app.services.system.audio_intel import AudioIntelligence
from app.services.system.perf_dashboard import PerformanceDashboard
from app.services.system.network_intel import NetworkIntelligence
from app.services.system.device_automation import DeviceAutomation

from datetime import datetime, timezone


def _env(tmp_path):
    engine, sf = create_session_factory(f"sqlite:///{tmp_path / 'p7.db'}")
    Base.metadata.create_all(engine)
    with sf() as db:
        db.add(User(id="u1", email="u1@example.com", password_hash="hash"))
        db.commit()
    return engine, sf


def test_app_launcher_search():
    al = AppLauncher()
    results = al.search("vscode")
    assert len(results) >= 1
    assert results[0]["alias"] == "vscode"


def test_app_launcher_search_partial():
    al = AppLauncher()
    assert any(r["alias"] == "chrome" for r in al.search("chrom"))
    assert al.search("") == []


def test_app_launcher_suggest():
    assert len(AppLauncher().suggest()) >= 3


def test_media_valid_actions():
    assert "play_pause" in VALID_ACTIONS
    assert "next" in VALID_ACTIONS


def test_media_invalid_action():
    r = MediaController().control("teleport")
    assert r["status"] == "error"
    assert "valid" in r


def test_audio_devices_graceful():
    d = AudioIntelligence().devices()
    assert isinstance(d, list)


def test_audio_set_volume_clamps():
    r = AudioIntelligence().set_volume(500)
    # should never raise; either ok or error
    assert r["status"] in ("ok", "error")


def test_perf_snapshot_shape():
    s = PerformanceDashboard().snapshot()
    assert s["status"] in ("ok", "error")
    if s["status"] == "ok":
        assert "cpu" in s
        assert "memory" in s
        assert "disk" in s


def test_network_local_info():
    n = NetworkIntelligence().local_info()
    assert n["status"] == "ok"
    assert "hostname" in n


def test_network_ping_graceful():
    n = NetworkIntelligence().ping("127.0.0.1")
    assert n["status"] in ("ok", "unreachable", "error")


def test_device_automation_list_empty(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        assert DeviceAutomation(db).list("u1") == []
    engine.dispose()


def test_device_automation_issue_unknown(tmp_path):
    engine, sf = _env(tmp_path)
    with sf() as db:
        r = DeviceAutomation(db).issue("u1", "nope", "wake")
        assert r["status"] == "error"
    engine.dispose()
